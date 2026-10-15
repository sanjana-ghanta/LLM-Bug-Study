import csv, json, os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MODELS = ["glm-5.3-thinking", "deepseek-v4-flash-thinking", "gpt-oss-thinking"]
CFG = {"java": ("results/java", ""), "python": ("results/python", "_python")}
for lang, (rdir, inf) in CFG.items():
    for m in MODELS:
        main = f"{ROOT}/{rdir}/results_fivetier{inf}_{m}.csv"
        out = f"{ROOT}/{rdir}/results_fivetier{inf}_{m}__t5-claude-sonnet-win.csv"
        rows = list(csv.DictReader(open(main))); hdr = list(rows[0].keys())
        keep = [r for r in rows if str(r["tier"]) != "5"]
        n1 = len(keep)
        if os.path.exists(out):
            keep += [r for r in csv.DictReader(open(out)) if str(r["tier"]) == "5"]
        tmp = out + ".tmp"
        w = csv.DictWriter(open(tmp, "w", newline=""), fieldnames=hdr, extrasaction="ignore"); w.writeheader(); w.writerows(keep)
        os.replace(tmp, out)
        fo = main.replace(".csv", "_failures.json"); fn = out.replace(".csv", "_failures.json")
        if os.path.exists(fo):
            old = json.load(open(fn)) if os.path.exists(fn) else {}
            new = {k: v for k, v in json.load(open(fo)).items() if not k.endswith("|5")}
            new.update({k: v for k, v in old.items() if k.endswith("|5")})
            json.dump(new, open(fn, "w"))
        print(lang, m, "T1-3 rows", n1, "+ T4 rows", len(keep) - n1)
