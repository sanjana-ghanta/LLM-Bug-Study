import os, glob, json, collections
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "make_tables.py")).read().split("raw = collections.Counter()")[0]
ns = {"__name__": "mt", "__file__": os.path.join(HERE, "make_tables.py")}
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()): exec(compile(src, "make_tables_head", "exec"), ns)
LANGS, MODELS, BASE, usable_set, load_five = ns["LANGS"], ns["MODELS"], ns["BASE"], ns["usable_set"], ns["load_five"]
W = "claude-sonnet-win"
res = {}
for lang, cfg in LANGS.items():
    U = usable_set(cfg["data"])
    have = set()
    mut = set()
    for f in glob.glob(os.path.join(BASE, cfg["data"], "*", "data.json")):
        _d = json.load(open(f)); _k = os.path.basename(os.path.dirname(f))
        if (_d.get("tier5_code_by_model") or {}).get(W): have.add(_k)
        if _d.get("tier3_code") and _d.get("tier3_mutation_line") is not None: mut.add(_k)
    for m in MODELS:
        pm = os.path.join(BASE, cfg["res"], cfg["five"].format(m=m))
        d = load_five(pm, U, collections.Counter())[0]
        pw = pm.replace(".csv", f"__t5-{W}.csv")
        w = load_five(pw, U, collections.Counter())[0] if os.path.exists(pw) else {}
        n1 = sum(1 for k in d if k[2] == "1"); n2 = sum(1 for k in d if k[2] == "2")
        e3 = {(p, b) for (p, b, t), v in d.items() if t == "1" and v is True and f"{p}_{b}" in mut}
        n3 = sum(1 for (p, b) in e3 if (p, b, "3") in d)
        e4 = {(p, b) for (p, b, t), v in d.items() if t == "2" and v is True and f"{p}_{b}" in have}
        n4 = sum(1 for (p, b) in e4 if (p, b, "5") in w)
        res[(lang, m)] = [(n1, len(U)), (n2, len(U)), (n3, len(e3)), (n4, len(e4))]
def cell(n, e):
    if e == 0: return "-"
    s = f"{n}/{e} ({100*n/e:.0f}%)"
    return f"**{s}**" if n / e < 0.9 else s
names = {"glm-5.3-thinking": "GLM", "deepseek-v4-flash-thinking": "DeepSeek", "gpt-oss-thinking": "GPT-OSS"}
hdr = ["Model"] + [f"{'Java' if l=='java' else 'Py'} T{t}" for l in ("java", "python") for t in (1, 2, 3, 4)]
print("| " + " | ".join(hdr) + " |"); print("|" + "---|" * len(hdr))
tsv = ["\t".join(hdr)]
for m in MODELS:
    row = [cell(n, e) for l in ("java", "python") for (n, e) in res[(l, m)]]
    print("| " + names.get(m, m) + " | " + " | ".join(row) + " |")
    tsv.append("\t".join([names.get(m, m)] + [c.replace("**", "") for c in row]))
open("completeness_table.tsv", "w").write("\n".join(tsv) + "\n")
print("\n(tsv saved to completeness_table.tsv; bold = under 90%)")
