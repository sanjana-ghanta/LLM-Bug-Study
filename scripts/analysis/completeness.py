import csv, json, os
B = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
M = ["glm-5.3-thinking", "deepseek-v4-flash-thinking", "gpt-oss-thinking"]
L = {"java": ("data/bugs", "results/java", "results_fivetier_{m}.csv"),
     "python": ("data/pybugs", "results/python", "results_fivetier_python_{m}.csv")}
def rows(p):
    d = {}
    if os.path.exists(p):
        for r in csv.DictReader(open(p)):
            d.setdefault((r["project"], str(r["bug_id"]), r["tier"]), r["correct"].strip().lower() == "true")
    return d
def fails(p):
    p = p.replace(".csv", "_failures.json")
    return json.load(open(p)) if os.path.exists(p) else {}
for lang, (dd, rd, tpl) in L.items():
    bugs = {}
    for d in sorted(os.listdir(f"{B}/{dd}")):
        p = f"{B}/{dd}/{d}/data.json"
        if os.path.exists(p):
            j = json.load(open(p))
            if j.get("original_bug_line") is not None:
                bugs[(j["project"], str(j["bug_id"]))] = j
    print(f"\n{lang.upper()}  usable bugs {len(bugs)}   (cells: missing (of which given up))")
    print(f"{'model':<28}{'T1':>10}{'T2':>10}{'T3':>10}{'T4 GLM-wr':>12}{'T4 Claude-wr':>14}")
    for m in M:
        pm = f"{B}/{rd}/{tpl.format(m=m)}"; pc = pm.replace(".csv", "__t5-claude-sonnet.csv")
        R, RC, F, FC = rows(pm), rows(pc), fails(pm), fails(pc)
        cnt = {k: [0, 0] for k in ("T1", "T2", "T3", "T4g", "T4c")}
        def chk(name, tier, have, FF, p, b):
            if (p, b, tier) in have: return
            cnt[name][0] += 1
            if FF.get(f"{p}|{b}|{tier}", 0) >= 3: cnt[name][1] += 1
        for (p, b), j in bugs.items():
            chk("T1", "1", R, F, p, b); chk("T2", "2", R, F, p, b)
            if R.get((p, b, "1")) and j.get("tier3_code"): chk("T3", "3", R, F, p, b)
            t5 = j.get("tier5_code_by_model") or {}
            if R.get((p, b, "2")):
                if t5.get("glm-5.3-thinking") or j.get("tier5_code"): chk("T4g", "5", R, F, p, b)
                if t5.get("claude-sonnet"): chk("T4c", "5", RC, FC, p, b)
        f = lambda k: f"{cnt[k][0]} ({cnt[k][1]})"
        print(f"{m:<28}{f('T1'):>10}{f('T2'):>10}{f('T3'):>10}{f('T4g'):>12}{f('T4c'):>14}")
