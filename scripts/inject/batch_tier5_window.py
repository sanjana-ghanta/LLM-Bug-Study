#!/usr/bin/env python3
"""Tier-4 disguises written on the SAME +-60-line window Tier 2 shows (matched view).
  copyshort -> reuse existing claude-sonnet rewrites that already fit in <=120 lines
  submit    -> batch-rewrite the windows for every other T2-solved bug
  status / collect as before. Writer key: claude-sonnet-win
"""
import argparse, csv, glob, json, os, datetime
import anthropic
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OLD, WRITER_KEY = "claude-sonnet", "claude-sonnet-win"
DEFAULT_MODEL_ID = "claude-sonnet-5-5"
MAX_TOKENS = int(os.environ.get("T5_MAX_TOKENS", "7000"))
WINDOW = 60
SYSTEM = "You are a precise code transformation tool. Follow instructions exactly."
MODELS = ["glm-5.3-thinking", "deepseek-v4-flash-thinking", "gpt-oss-thinking"]
LANGS = {"java": ("data/bugs", "results/java", "Java"), "python": ("data/pybugs", "results/python", "Python")}
BATCH_LOG = os.path.join(ROOT, "batch_logs/batches_tier5_win.json")
def ok(v): return str(v).strip().lower() in ("true", "1", "yes")
def nl(s): return s.count("\n") + 1

def window(code, c):
    L = code.splitlines()
    if len(L) <= 2 * WINDOW: return "\n".join(L), 1, len(L)
    lo = max(0, c - 1 - WINDOW); hi = min(len(L), c - 1 + WINDOW + 1)
    return "\n".join(L[lo:hi]), lo + 1, hi

def build_prompt(lang, file_path, snippet):
    n = LANGS[lang][2]
    return f"""You are a {n} code transformation tool.
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

def load_all(lang):
    ddir = LANGS[lang][0]
    for f in sorted(glob.glob(os.path.join(ROOT, ddir, "*", "data.json"))):
        yield os.path.basename(os.path.dirname(f)), f, json.load(open(f))

def needed_keys(lang):
    rdir = LANGS[lang][1]; s = set()
    for m in MODELS:
        for p in glob.glob(os.path.join(ROOT, rdir, f"results_fivetier*{m}*.csv")):
            for r in csv.DictReader(open(p)):
                if str(r.get("tier")) == "2" and ok(r.get("correct")): s.add(f"{r['project']}_{r['bug_id']}")
    return s

def cmd_copyshort(a):
    n = 0
    for k, f, d in load_all(a.lang):
        old = (d.get("tier5_code_by_model") or {}).get(OLD)
        if old and nl(old) <= 2 * WINDOW and not (d.get("tier5_code_by_model") or {}).get(WRITER_KEY):
            d["tier5_code_by_model"][WRITER_KEY] = old
            d.setdefault("tier5_meta_by_model", {})[WRITER_KEY] = {"copied_from": OLD, "window": "whole-file(<=120)"}
            json.dump(d, open(f, "w"), indent=2); n += 1
    print("copied short rewrites:", n)

def select(lang):
    need = needed_keys(lang); out = {}
    for k, f, d in load_all(lang):
        if k not in need or d.get("original_bug_line") is None or not d.get("buggy_code"): continue
        if (d.get("tier5_code_by_model") or {}).get(WRITER_KEY): continue
        out[k] = (f, d)
    return out

def cmd_submit(a):
    sel = select(a.lang); reqs = []; spans = {}
    for k, (f, d) in sorted(sel.items()):
        snip, lo, hi = window(d["buggy_code"], int(d["original_bug_line"])); spans[k] = [lo, hi]
        reqs.append({"custom_id": k, "params": {"model": a.model_id, "max_tokens": MAX_TOKENS, "system": SYSTEM,
            "messages": [{"role": "user", "content": build_prompt(a.lang, d["file_path"], snip)}]}})
    if a.limit: reqs = reqs[:a.limit]
    print(f"{len(reqs)} windowed requests, model={a.model_id}, max_tokens={MAX_TOKENS}, first: {[r['custom_id'] for r in reqs[:5]]}")
    if a.dry_run or not reqs: return
    b = anthropic.Anthropic().messages.batches.create(requests=reqs)
    log = json.load(open(BATCH_LOG)) if os.path.exists(BATCH_LOG) else []
    log.append({"id": b.id, "lang": a.lang, "model_id": a.model_id, "n": len(reqs), "spans": spans, "created": datetime.datetime.now().isoformat()})
    json.dump(log, open(BATCH_LOG, "w"), indent=2); print("submitted batch", b.id)

def pick(a):
    log = json.load(open(BATCH_LOG))
    return next((x for x in log if x["id"] == a.batch_id), None) if a.batch_id else log[-1]

def cmd_status(a):
    info = pick(a); b = anthropic.Anthropic().messages.batches.retrieve(info["id"]); print(info["id"], b.processing_status, b.request_counts)

def extract_code(raw):
    import re
    mm = re.search(r"```[A-Za-z0-9_+-]*\n(.*?)```", raw, re.S)
    return (mm.group(1) if mm else raw).strip("\n")

def cmd_collect(a):
    info = pick(a); c = anthropic.Anthropic(); b = c.messages.batches.retrieve(info["id"])
    if b.processing_status != "ended": print("not finished:", b.processing_status, b.request_counts); return
    ddir = LANGS[info["lang"]][0]; saved = trunc = err = short = long_ = tin = tout = 0
    for r in c.messages.batches.results(info["id"]):
        if r.result.type != "succeeded": err += 1; print("ERR", r.custom_id, r.result.type); continue
        m = r.result.message; tin += m.usage.input_tokens; tout += m.usage.output_tokens
        if m.stop_reason == "max_tokens": trunc += 1; print("TRUNCATED", r.custom_id); continue
        text = extract_code("".join(x.text for x in m.content if x.type == "text"))
        path = os.path.join(ROOT, ddir, r.custom_id, "data.json"); d = json.load(open(path))
        lo, hi = info["spans"][r.custom_id]
        if nl(text) < 0.6 * (hi - lo + 1): short += 1; print("SHORT", r.custom_id); continue
        if nl(text) > 2 * WINDOW + 40: long_ += 1; print("LONG(still saved)", r.custom_id, nl(text))
        d.setdefault("tier5_code_by_model", {})[WRITER_KEY] = text
        d.setdefault("tier5_meta_by_model", {})[WRITER_KEY] = {"model_id": m.model, "stop_reason": m.stop_reason, "window": [lo, hi], "lines": nl(text)}
        json.dump(d, open(path, "w"), indent=2); saved += 1
    print(f"saved={saved} truncated={trunc} errors={err} short={short} long={long_}")
    print(f"tokens in={tin} out={tout} est batch cost ~${(tin*1 + tout*5)/1e6:.2f}")

p = argparse.ArgumentParser(); sp = p.add_subparsers(dest="cmd", required=True)
s = sp.add_parser("copyshort"); s.add_argument("--lang", required=True, choices=list(LANGS)); s.set_defaults(f=cmd_copyshort)
s = sp.add_parser("submit"); s.add_argument("--lang", required=True, choices=list(LANGS)); s.add_argument("--limit", type=int, default=0)
s.add_argument("--model-id", default=DEFAULT_MODEL_ID); s.add_argument("--dry-run", action="store_true"); s.set_defaults(f=cmd_submit)
for n, fn in (("status", cmd_status), ("collect", cmd_collect)):
    t = sp.add_parser(n); t.add_argument("--batch-id"); t.set_defaults(f=fn)
a = p.parse_args(); a.f(a)
