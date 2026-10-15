import csv, glob, json, os
for lang, dd in (("java", "data/bugs"), ("python", "data/pybugs")):
    for m in ("glm-5.3-thinking", "deepseek-v4-flash-thinking", "gpt-oss-thinking"):
        mf = f"results/tier2_misses/tier2_misses_{lang}_{m}.txt"
        if not os.path.exists(mf):
            print(f"{lang:7}{m:28} no miss list yet"); continue
        misses = [l.strip().replace("-", "_") for l in open(mf) if l.strip()]
        exp = 0
        for k in misses:
            p = f"{dd}/{k}/data.json"
            if not os.path.exists(p): continue
            j = json.load(open(p))
            if j.get("original_bug_line") is None: continue
            if len(j.get("buggy_code", "").splitlines()) > 1000: continue
            exp += 1
        out = []
        for tag in ("exp6", "exp7"):
            got = set()
            for f in glob.glob(f"results/{lang}/*{tag}*{m}.csv"):
                for r in csv.DictReader(open(f)):
                    if r["tier"] == "2": got.add(f"{r['project']}_{r['bug_id']}")
            got &= set(misses)
            out.append(f"{tag} {len(got)}/{exp} ({100*len(got)/exp:.0f}%)" if exp else f"{tag} n/a")
        print(f"{lang:7}{m:28} misses {len(misses):4} | eligible {exp:4} | " + " | ".join(out))
