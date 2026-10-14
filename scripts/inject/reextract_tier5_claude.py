#!/usr/bin/env python3
"""Re-extract every Claude tier-5 rewrite from the stored raw batch output (free) with a robust extractor."""
import anthropic, ast, json, os, re
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WRITER = "claude-sonnet"
DATA = {"java": "data/bugs", "python": "data/pybugs"}

def extract_code(raw):
    t = re.sub(r"^(?:\s*<invoke[^>]*>.*?</invoke>\s*)+", "", raw.strip(), flags=re.S).strip()
    lines = t.split("\n")
    if lines and lines[0].lstrip().startswith("```"):
        lines = lines[1:]
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip() == "```":
                lines = lines[:i]
                break
    else:
        while lines and lines[-1].strip() == "```":
            lines.pop()
    return "\n".join(lines).strip()

def struct_ok(code, lang):
    if lang == "java":
        t = re.sub(r"/\*.*?\*/", "", code, flags=re.S); t = re.sub(r"//[^\n]*", "", t)
        t = re.sub(r'"(\\.|[^"\\\n])*"', '""', t); t = re.sub(r"'(\\.|[^'\\\n])*'", "''", t)
        return t.count("{") == t.count("}") and t.count("{") > 0
    try: ast.parse(code); return True
    except Exception: return False

def code_lines(s, lang):
    marks = ("//", "*", "/*") if lang == "java" else ("#",)
    return sum(1 for l in s.splitlines() if l.strip() and not l.strip().startswith(marks))

c = anthropic.Anthropic()
for info in json.load(open(os.path.join(ROOT, "batches_tier5.json"))):
    lang = info["lang"]; saved = skipped = 0; flagged = []
    for r in c.messages.batches.results(info["id"]):
        if r.result.type != "succeeded": skipped += 1; continue
        m = r.result.message
        if m.stop_reason == "max_tokens": skipped += 1; print("TRUNCATED", r.custom_id); continue
        raw = "".join(x.text for x in m.content if x.type == "text")
        code = extract_code(raw)
        path = os.path.join(ROOT, DATA[lang], r.custom_id, "data.json"); d = json.load(open(path))
        ok = struct_ok(code, lang); orig_ok = struct_ok(d["buggy_code"], lang)
        ratio = code_lines(code, lang) / max(1, code_lines(d["buggy_code"], lang))
        d.setdefault("tier5_code_by_model", {})[WRITER] = code
        d.setdefault("tier5_meta_by_model", {})[WRITER] = {"model_id": m.model, "stop_reason": m.stop_reason, "struct_ok": ok}
        json.dump(d, open(path, "w"), indent=2); saved += 1
        bad = (orig_ok and not ok) or ratio < 0.8 or ratio > 1.4 or "<invoke" in code or "<parameter" in code \
              or code.startswith("```") or code.endswith("```")
        if bad: flagged.append((r.custom_id, "struct" if (orig_ok and not ok) else "", round(ratio, 2)))
    print(f"{info['id']} ({lang}): saved={saved} skipped={skipped} flagged={len(flagged)}")
    for x in flagged: print("   ", x)
