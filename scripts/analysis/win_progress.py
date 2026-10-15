import csv, glob, json, os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MODELS = ["glm-5.3-thinking", "deepseek-v4-flash-thinking", "gpt-oss-thinking"]
CFG = {"java": ("data/bugs", "results/java", ""), "python": ("data/pybugs", "results/python", "_python")}
W = "claude-sonnet-win"
for lang, (ddir, rdir, inf) in CFG.items():
    have = set()
    for f in glob.glob(f"{ROOT}/{ddir}/*/data.json"):
        if (json.load(open(f)).get("tier5_code_by_model") or {}).get(W): have.add(os.path.basename(os.path.dirname(f)))
    for m in MODELS:
        p = f"{ROOT}/{rdir}/results_fivetier{inf}_{m}__t5-{W}.csv"
        rows = list(csv.DictReader(open(p)))
        t2 = {f"{r['project']}_{r['bug_id']}" for r in rows if str(r["tier"]) == "2" and str(r["correct"]).lower() in ("true", "1")}
        elig = t2 & have
        done = {f"{r['project']}_{r['bug_id']}" for r in rows if str(r["tier"]) == "5"} & elig
        print(f"{lang:7s}{m:30s} T4 done {len(done):4d} / eligible {len(elig):4d}  ({100*len(done)//max(1,len(elig))}%)")
