import json, os, re, collections
D = "data/pybugs"
P = os.path.expanduser("~/bugsinpy_workspace/BugsInPy/projects")
out, off = {}, collections.Counter()
multi = wrongfile = nomatch = n = 0
for d in sorted(os.listdir(D)):
    dj = os.path.join(D, d, "data.json")
    if not os.path.exists(dj):
        continue
    j = json.load(open(dj))
    proj, bid, fp = j["project"], j["bug_id"], j.get("file_path", "")
    stored = j.get("original_bug_line")
    pp = f"{P}/{proj}/bugs/{bid}/bug_patch.txt"
    if not os.path.exists(pp) or not stored:
        continue
    n += 1
    files, cur, oldl, true = [], None, None, None
    for ln in open(pp, errors="ignore").read().splitlines():
        if ln.startswith("diff --git"):
            cur = ln.split(" b/")[-1]; files.append(cur); oldl = None; continue
        m = re.match(r"@@ -(\d+)", ln)
        if m:
            oldl = int(m.group(1)); continue
        if oldl is None or ln.startswith(("---", "+++")):
            continue
        if ln.startswith(" "):
            oldl += 1
        elif ln.startswith(("-", "+")):
            if true is None and cur and (cur.endswith(fp) or fp.endswith(cur)):
                true = oldl
    if len(files) > 1: multi += 1
    if files and not (files[0].endswith(fp) or fp.endswith(files[0])): wrongfile += 1
    if true is None:
        nomatch += 1; continue
    out[f"{proj}_{bid}"] = {"stored": stored, "true": true}
    off[stored - true] += 1
json.dump(out, open("results/python/true_bug_lines.json", "w"), indent=1)
print("bugs", n, "| multi-file patches", multi, "| first hunk in different file", wrongfile, "| no match", nomatch)
print("stored minus true (top):", sorted(off.items(), key=lambda x: -x[1])[:12])
