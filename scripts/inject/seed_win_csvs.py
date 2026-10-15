import csv, glob, json, os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MODELS = ["glm-5.3-thinking", "deepseek-v4-flash-thinking", "gpt-oss-thinking"]
CFG = {"java": ("data/bugs", "results/java", ""), "python": ("data/pybugs", "results/python", "_python")}
OLD, NEW = "claude-sonnet", "claude-sonnet-win"
for lang, (ddir, rdir, inf) in CFG.items():
    ok_bug = set()
    for f in glob.glob(os.path.join(ROOT, ddir, "*", "data.json")):
        d = json.load(open(f)); t = d.get("tier5_code_by_model") or {}
        if t.get(NEW) and (t.get(OLD) == t.get(NEW)): ok_bug.add(os.path.basename(os.path.dirname(f)))
    for m in MODELS:
        main = f"{ROOT}/{rdir}/results_fivetier{inf}_{m}.csv"
        oldt5 = f"{ROOT}/{rdir}/results_fivetier{inf}_{m}__t5-{OLD}.csv"
        out = f"{ROOT}/{rdir}/results_fivetier{inf}_{m}__t5-{NEW}.csv"
        if not os.path.exists(main): print("missing", main); continue
        if os.path.exists(out): print("exists, skipping", out); continue
        rows = list(csv.DictReader(open(main))); hdr = list(rows[0].keys())
        keep = [r for r in rows if str(r["tier"]) != "5"]
        if os.path.exists(oldt5):
            keep += [r for r in csv.DictReader(open(oldt5)) if str(r["tier"]) == "5" and f"{r['project']}_{r['bug_id']}" in ok_bug]
        w = csv.DictWriter(open(out, "w", newline=""), fieldnames=hdr, extrasaction="ignore"); w.writeheader(); w.writerows(keep)
        fo = f"{ROOT}/{rdir}/results_fivetier{inf}_{m}_failures.json"; fn = out.replace(".csv", "_failures.json")
        if os.path.exists(fo) and not os.path.exists(fn):
            fj = json.load(open(fo)); json.dump({k: v for k, v in fj.items() if not k.endswith("|5")}, open(fn, "w"))
        print(lang, m, "seeded", len(keep), "rows ->", os.path.basename(out))
