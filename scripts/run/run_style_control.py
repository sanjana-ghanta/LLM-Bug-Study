#!/usr/bin/env python3
"""
Rewrite style control (one command, any OpenAI-compatible model).

Question: does rewriting alone change a model's verdicts?  We take N clean (patched) code windows per
language, show the model each window twice -- once as-is ("raw") and once rewritten by Claude Sonnet with
the same instructions used for the T2 rewrites ("rewrite") -- and compare the two sets of verdicts per
bug with an exact McNemar test.  The patched code has no documented bug, so NO BUG is the expected answer.

Usage (from the repo root):
    export MODEL_NAME='GPT-5.5'                 # name registered in scripts/lib/config.py, or any new name
    read -rs MODEL_API_KEY && export MODEL_API_KEY
    export MODEL_BASE_URL='https://...'         # only needed if MODEL_NAME is not already in config.py
    export MODEL_ID='...'                       # only needed if MODEL_NAME is not already in config.py
    export ANTHROPIC_API_KEY='...'              # only needed to CREATE the rewrites (once; they are cached)

    python3 scripts/run/run_style_control.py -n 2 --dry-run      # show the chosen bugs, no API calls
    python3 scripts/run/run_style_control.py -n 2                # smoke test (2 bugs per language)
    python3 scripts/run/run_style_control.py -n 50               # the real run
    python3 scripts/run/run_style_control.py --summarize-only    # recompute the McNemar table from the CSV

The bugs are the same random sample as `-n N --seed 0` in the detection runners (usable bugs only).
Re-running is safe: finished rewrites and verdicts are skipped.
Outputs (results/style_control/): rewrites_<lang>.json (cached rewrites, reusable by any model),
style_control_<model>.csv (verdicts), summary_<model>.txt (McNemar table).
"""
import argparse, csv, json, math, os, random, re, sys, threading, time
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

LANGS = {"java": ("data/bugs", "Java"), "python": ("data/pybugs", "Python")}
WINDOW = 60
DET_SYSTEM = "You are a careful code reviewer."
REWRITE_SYSTEM = "You are a precise code transformation tool. Follow instructions exactly."
REWRITE_MODEL_ID = "claude-sonnet-5-5"
REWRITE_MAX_TOKENS = int(os.environ.get("T5_MAX_TOKENS", "7000"))
DET_MAX_TOKENS = int(os.environ.get("DET_MAX_TOKENS", "32000"))
LOCK = threading.Lock()


# ----------------------------------------------------------------- shared logic (copied from the repo's runners)
def window(code, c):
    """Same +-60-line window the T2 rewrites use (whole file if <= 120 lines). Returns (text, first, last)."""
    L = code.splitlines()
    if len(L) <= 2 * WINDOW:
        return "\n".join(L), 1, len(L)
    lo = max(0, c - 1 - WINDOW)
    hi = min(len(L), c - 1 + WINDOW + 1)
    return "\n".join(L[lo:hi]), lo + 1, hi


def rewrite_prompt(lang_name, file_path, snippet):
    return f"""You are a {lang_name} code transformation tool.
The code below is an excerpt of a larger file and may begin or end in the middle of a method or class. Do NOT complete it, do not add imports, package lines or closing braces that are not already there.
Rewrite the excerpt so that:
1. The code looks different on the surface (rename local variables, restructure expressions, change loop styles)
2. The semantic behavior is IDENTICAL - including any bugs present
3. Do not fix any bugs - preserve them exactly
4. Keep roughly the same number of lines
5. Return ONLY the rewritten code with no explanation

File: {file_path}

Code:
{snippet}"""


def detection_prompt(lang_name, file_path, code):
    return f"""Review the following {lang_name} code from {file_path} and determine if it contains a bug.
Respond in this exact format:
VERDICT: BUG or NO BUG
REASON: <one sentence explanation>

Code:
{code}"""


def extract_code(raw):
    m = re.search(r"```[A-Za-z0-9_+-]*\n(.*?)```", raw, re.S)
    return (m.group(1) if m else raw).strip("\n")


def nl(s):
    return s.count("\n") + 1


# ----------------------------------------------------------------- bug selection
def usable_dirs(datadir):
    out = []
    for d in sorted(os.listdir(os.path.join(ROOT, datadir))):
        p = os.path.join(ROOT, datadir, d, "data.json")
        if not os.path.exists(p):
            continue
        try:
            j = json.load(open(p))
        except Exception:
            continue
        if j.get("original_bug_line") is not None and j.get("patched_code"):
            out.append(d)
    return out


def select(lang, n, seed):
    dirs = usable_dirs(LANGS[lang][0])
    return sorted(random.Random(seed).sample(dirs, min(n, len(dirs))))


def load_bug(lang, key):
    return json.load(open(os.path.join(ROOT, LANGS[lang][0], key, "data.json")))


# ----------------------------------------------------------------- rewrites (Claude Sonnet, cached)
def rewrite_one(lang, key, rewrite_model_id):
    """Returns a cache entry dict for one bug (with 'rewrite' = None if the rewrite is unusable)."""
    import anthropic
    d = load_bug(lang, key)
    raw, lo, hi = window(d["patched_code"], int(d["original_bug_line"]))
    entry = {"file_path": d["file_path"], "raw": raw, "span": [lo, hi], "rewrite": None}
    msg = anthropic.Anthropic().messages.create(
        model=rewrite_model_id, max_tokens=REWRITE_MAX_TOKENS, system=REWRITE_SYSTEM,
        messages=[{"role": "user", "content": rewrite_prompt(LANGS[lang][1], d["file_path"], raw)}])
    text = extract_code("".join(b.text for b in msg.content if getattr(b, "type", "") == "text"))
    entry["stop_reason"], entry["model_id"] = msg.stop_reason, msg.model
    if msg.stop_reason == "max_tokens":
        entry["skip"] = "truncated"
    elif nl(text) < 0.6 * (hi - lo + 1):
        entry["skip"] = "too short"
    else:
        entry["rewrite"] = text
    return entry


def ensure_rewrites(lang, keys, out_dir, rewrite_model_id, workers):
    path = os.path.join(out_dir, f"rewrites_{lang}.json")
    cache = json.load(open(path)) if os.path.exists(path) else {}
    todo = [k for k in keys if k not in cache]
    if todo:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            sys.exit(f"ERROR: {len(todo)} {lang} rewrites are missing and ANTHROPIC_API_KEY is not set "
                     f"(only needed to create the rewrites; once created they are cached in {path}).")
        print(f"[{lang}] writing {len(todo)} rewrites with {rewrite_model_id} ...", flush=True)

        def job(k):
            try:
                return k, rewrite_one(lang, k, rewrite_model_id)
            except Exception as e:
                print(f"  Error calling rewrite model for {k}: {e}", flush=True)
                return k, None
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for k, e in ex.map(job, todo):
                if e is not None:
                    cache[k] = e
        os.makedirs(out_dir, exist_ok=True)
        json.dump(cache, open(path, "w"), indent=1)
    usable = [k for k in keys if cache.get(k, {}).get("rewrite")]
    skipped = [k for k in keys if k not in usable]
    if skipped:
        print(f"[{lang}] {len(skipped)} bugs without a usable rewrite are skipped: {skipped}", flush=True)
    return cache, usable


# ----------------------------------------------------------------- verdicts
def ask_model(model_key, lang_name, file_path, code, effort, call_llm):
    prompt = detection_prompt(lang_name, file_path, code)
    for attempt in range(3):
        try:
            text = call_llm(model_key, system_prompt=DET_SYSTEM, user_prompt=prompt,
                            max_tokens=DET_MAX_TOKENS, reasoning_effort=effort)
        except Exception as e:
            s = str(e).lower()
            if "rate limit" in s or "429" in s:
                print("  Rate limit hit, waiting 60s...", flush=True)
                time.sleep(60)
                continue
            print(f"  Error calling {model_key}: {e}", flush=True)
            time.sleep(5)
            continue
        if text:
            return ("BUG" if "VERDICT: BUG" in text else "NO BUG"), text
        print("  Empty response, retrying...", flush=True)
    return None, None


def read_done(csv_path):
    done = set()
    if os.path.exists(csv_path):
        for r in csv.DictReader(open(csv_path, newline="")):
            done.add((r["lang"], r["bug"], r["arm"]))
    return done


def run_verdicts(model_key, lang, usable, cache, csv_path, effort, workers, call_llm):
    done = read_done(csv_path)
    jobs = [(k, arm) for k in usable for arm in ("raw", "rewrite") if (lang, k, arm) not in done]
    print(f"[{lang}] {len(jobs)} model calls to make ({len(usable) * 2 - len(jobs)} already done)", flush=True)
    new_file = not os.path.exists(csv_path)
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    f = open(csv_path, "a", newline="")
    w = csv.writer(f)
    if new_file:
        w.writerow(["lang", "bug", "arm", "verdict", "response"])
        f.flush()

    def job(item):
        k, arm = item
        e = cache[k]
        code = e["raw"] if arm == "raw" else e["rewrite"]
        v, text = ask_model(model_key, LANGS[lang][1], e["file_path"], code, effort, call_llm)
        if v is None:
            return
        with LOCK:
            w.writerow([lang, k, arm, v, " ".join(text.split())[:1500]])
            f.flush()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(job, jobs))
    f.close()


# ----------------------------------------------------------------- McNemar summary
def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)


def summarize(model_key, csv_path, out_dir):
    if not os.path.exists(csv_path):
        sys.exit(f"no results file yet: {csv_path}")
    v = {}
    for r in csv.DictReader(open(csv_path, newline="")):
        v.setdefault((r["lang"], r["bug"]), {})[r["arm"]] = r["verdict"]
    lines = [f"Rewrite style control, model {model_key} (patched code; NO BUG is the expected verdict)",
             "lang    pairs  NO BUG raw  NO BUG rewrite  raw->rewrite lost  gained  exact McNemar p"]
    ps = []
    for lang in LANGS:
        pairs = [x for (l, _), x in v.items() if l == lang and "raw" in x and "rewrite" in x]
        if not pairs:
            continue
        a = sum(x["raw"] == "NO BUG" for x in pairs)
        b = sum(x["rewrite"] == "NO BUG" for x in pairs)
        lost = sum(x["raw"] == "NO BUG" and x["rewrite"] == "BUG" for x in pairs)      # raw right, rewrite wrong
        gain = sum(x["raw"] == "BUG" and x["rewrite"] == "NO BUG" for x in pairs)
        p = mcnemar_exact(lost, gain)
        ps.append(p)
        n = len(pairs)
        lines.append(f"{lang:<7} {n:>5}  {a:>4} ({100*a/n:4.1f}%)  {b:>4} ({100*b/n:4.1f}%)      "
                     f"{lost:>6}            {gain:>5}     {p:.3f}")
    if ps:
        lines.append(f"smallest p = {min(ps):.3f} over {len(ps)} comparisons")
    text = "\n".join(lines)
    print("\n" + text)
    open(os.path.join(out_dir, f"summary_{model_key}.txt"), "w").write(text + "\n")


# ----------------------------------------------------------------- main
def get_call_llm(model_key):
    from lib.config import MODELS
    from lib.llm_clients import call_llm
    if model_key not in MODELS:
        need = [v for v in ("MODEL_BASE_URL", "MODEL_ID", "MODEL_API_KEY") if not os.environ.get(v)]
        if need:
            sys.exit(f"ERROR: model '{model_key}' is not in scripts/lib/config.py and {', '.join(need)} is not set.")
        MODELS[model_key] = {"backend": "openai_compatible", "base_url": os.environ["MODEL_BASE_URL"],
                             "model_id": os.environ["MODEL_ID"], "api_key_env": "MODEL_API_KEY",
                             "api_key_header": os.environ.get("MODEL_API_KEY_HEADER") or None}
    return call_llm


def main(argv=None, call_llm=None):
    p = argparse.ArgumentParser(description="Rewrite style control (raw vs rewritten clean code) for one model.")
    p.add_argument("--model", default=os.environ.get("MODEL_NAME"), help="model name (default: $MODEL_NAME)")
    p.add_argument("-n", "--num-bugs", type=int, default=50)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--lang", choices=["java", "python", "both"], default="both")
    p.add_argument("--reasoning-effort", default="low", help="low|medium|high, or 'none' to not pass it")
    p.add_argument("--rewrite-model-id", default=REWRITE_MODEL_ID)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--out-dir", default=os.path.join(ROOT, "results", "style_control"))
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--summarize-only", action="store_true")
    a = p.parse_args(argv)
    if not a.model:
        sys.exit("ERROR: give --model or set MODEL_NAME")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", a.model):
        sys.exit("ERROR: model name may only contain letters, digits, '.', '_' and '-'")
    effort = None if a.reasoning_effort == "none" else a.reasoning_effort
    csv_path = os.path.join(a.out_dir, f"style_control_{a.model}.csv")
    if a.summarize_only:
        return summarize(a.model, csv_path, a.out_dir)
    langs = list(LANGS) if a.lang == "both" else [a.lang]
    plan = {lang: select(lang, a.num_bugs, a.seed) for lang in langs}
    for lang, keys in plan.items():
        print(f"[{lang}] {len(keys)} bugs, e.g. {keys[:5]}")
    if a.dry_run:
        return
    if call_llm is None:
        call_llm = get_call_llm(a.model)
    for lang, keys in plan.items():
        cache, usable = ensure_rewrites(lang, keys, a.out_dir, a.rewrite_model_id, a.workers)
        run_verdicts(a.model, lang, usable, cache, csv_path, effort, a.workers, call_llm)
    summarize(a.model, csv_path, a.out_dir)


if __name__ == "__main__":
    main()
