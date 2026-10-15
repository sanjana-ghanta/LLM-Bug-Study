#!/usr/bin/env python3
"""Tier-4 (internal tier 5) disguises written by Claude via the Message Batches API.
  submit  -> choose bugs, send one batch, remember its id
  status  -> show batch progress
  collect -> save finished rewrites into data.json under tier5_code_by_model[WRITER_KEY]
"""
import argparse, ast, csv, glob, json, os, re, datetime
import anthropic

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WRITER_KEY = "claude-sonnet"
DEFAULT_MODEL_ID = "claude-sonnet-5-5"
MAX_TOKENS = int(os.environ.get("T5_MAX_TOKENS", "7000"))
MAX_LINES = 1000
SYSTEM = "You are a precise code transformation tool. Follow instructions exactly."
MODELS = ["glm-5.3-thinking", "deepseek-v4-flash-thinking", "gpt-oss-thinking"]
LANGS = {"java": ("data/bugs", "results/java", "Java"), "python": ("data/pybugs", "results/python", "Python")}
BATCH_LOG = os.path.join(ROOT, "batch_logs/batches_tier5.json")
BT = chr(96) * 3

def ok(v): return str(v).strip().lower() in ("true", "1", "yes")

def build_prompt(lang, file_path, code):
    n = LANGS[lang][2]
    return f"""You are a {n} code transformation tool.
Rewrite the following {n} code so that:
1. The code looks different on the surface (rename variables, restructure expressions, change loop styles)
2. The semantic behavior is IDENTICAL - including any bugs present
3. Do not fix any bugs - preserve them exactly
4. Return ONLY the rewritten code with no explanation

File: {file_path}

Code:
{code}"""

def select_bugs(lang, limit):
    ddir, rdir, _ = LANGS[lang]
    cand = {}
    for f in glob.glob(os.path.join(ROOT, ddir, "*", "data.json")):
        d = json.load(open(f)); k = os.path.basename(os.path.dirname(f))
        code = d.get("buggy_code") or ""
        if d.get("original_bug_line") is None or code.count("\n") + 1 > MAX_LINES: continue
        if (d.get("tier5_code_by_model") or {}).get(WRITER_KEY): continue
        cand[k] = f
    needed = set()
    for m in MODELS:
        for p in glob.glob(os.path.join(ROOT, rdir, f"results_fivetier*{m}*.csv")):
            for r in csv.DictReader(open(p)):
                if str(r.get("tier")) == "2" and ok(r.get("correct")):
                    needed.add(f"{r['project']}_{r['bug_id']}")
    keys = sorted(k for k in cand if k in needed)
    if limit and limit < len(keys):
        keys = keys[::max(1, len(keys) // limit)][:limit]
    return keys, cand

def load_log():
    return json.load(open(BATCH_LOG)) if os.path.exists(BATCH_LOG) else []

def cmd_submit(a):
    keys, cand = select_bugs(a.lang, a.limit)
    reqs = []
    for k in keys:
        d = json.load(open(cand[k]))
        reqs.append({"custom_id": k, "params": {"model": a.model_id, "max_tokens": MAX_TOKENS, "system": SYSTEM,
            "messages": [{"role": "user", "content": build_prompt(a.lang, d["file_path"], d["buggy_code"])}]}})
    print(f"{len(reqs)} requests, model={a.model_id}, max_tokens={MAX_TOKENS}, first: {keys[:5]}")
    if a.dry_run or not reqs: return
    b = anthropic.Anthropic().messages.batches.create(requests=reqs)
    log = load_log()
    log.append({"id": b.id, "lang": a.lang, "model_id": a.model_id, "n": len(reqs), "created": datetime.datetime.now().isoformat()})
    json.dump(log, open(BATCH_LOG, "w"), indent=2)
    print("submitted batch", b.id)

def pick(a):
    log = load_log()
    if not log: raise SystemExit("no batches recorded")
    return next((x for x in log if x["id"] == a.batch_id), None) if a.batch_id else log[-1]

def cmd_status(a):
    info = pick(a); b = anthropic.Anthropic().messages.batches.retrieve(info["id"])
    print(info["id"], b.processing_status, b.request_counts)

def extract_code(raw):
    mm = re.search(r"```[A-Za-z0-9_+-]*\n(.*?)```", raw, re.S)
    return (mm.group(1) if mm else raw).strip()

def struct_ok(code, lang):
    if lang == "java":
        t = re.sub(r"/\*.*?\*/", "", code, flags=re.S); t = re.sub(r"//[^\n]*", "", t)
        t = re.sub(r'"(\\.|[^"\\\n])*"', '""', t); t = re.sub(r"'(\\.|[^'\\\n])*'", "''", t)
        return t.count("{") == t.count("}") and t.count("{") > 0
    try: ast.parse(code); return True
    except Exception: return False

def cmd_collect(a):
    info = pick(a); c = anthropic.Anthropic()
    b = c.messages.batches.retrieve(info["id"])
    if b.processing_status != "ended": print("not finished yet:", b.processing_status, b.request_counts); return
    ddir = LANGS[info["lang"]][0]
    saved = trunc = err = short = tin = tout = 0
    for r in c.messages.batches.results(info["id"]):
        if r.result.type != "succeeded": err += 1; print("ERR", r.custom_id, r.result.type); continue
        m = r.result.message; tin += m.usage.input_tokens; tout += m.usage.output_tokens
        if m.stop_reason == "max_tokens": trunc += 1; print("TRUNCATED", r.custom_id); continue
        text = extract_code("".join(x.text for x in m.content if x.type == "text"))
        path = os.path.join(ROOT, ddir, r.custom_id, "data.json"); d = json.load(open(path))
        if text.count("\n") + 1 < 0.5 * (d["buggy_code"].count("\n") + 1): short += 1; print("SHORT", r.custom_id)
        d.setdefault("tier5_code_by_model", {})[WRITER_KEY] = text
        d.setdefault("tier5_meta_by_model", {})[WRITER_KEY] = {"model_id": m.model, "stop_reason": m.stop_reason, "struct_ok": struct_ok(text, info["lang"])}
        json.dump(d, open(path, "w"), indent=2); saved += 1
    print(f"saved={saved} truncated={trunc} errors={err} suspiciously_short={short}")
    print(f"tokens in={tin} out={tout}  est batch cost ~${(tin*1 + tout*5)/1e6:.2f} (Sonnet 5.5 batch: $1 in / $5 out per M)")

p = argparse.ArgumentParser(); sp = p.add_subparsers(dest="cmd", required=True)
s = sp.add_parser("submit"); s.add_argument("--lang", required=True, choices=list(LANGS)); s.add_argument("--limit", type=int, default=0)
s.add_argument("--model-id", default=DEFAULT_MODEL_ID); s.add_argument("--dry-run", action="store_true"); s.set_defaults(f=cmd_submit)
for n, fn in (("status", cmd_status), ("collect", cmd_collect)):
    t = sp.add_parser(n); t.add_argument("--batch-id"); t.set_defaults(f=fn)
a = p.parse_args(); a.f(a)
