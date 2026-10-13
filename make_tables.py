import csv, json, os, collections, math
BASE = os.path.expanduser("~/llm-bug-study")
MODELS = ["glm-5.3-thinking", "deepseek-v4-flash-thinking", "gpt-oss-thinking"]
LANGS = {
    "java":   dict(data="data/bugs",   res="results/java",   five="results_fivetier_{m}.csv",
                   p6="results_exp6_bugid_recall_{m}.csv",        p7="results_exp7_context_framing_{m}.csv"),
    "python": dict(data="data/pybugs", res="results/python", five="results_fivetier_python_{m}.csv",
                   p6="results_exp6_bugid_recall_python_{m}.csv", p7="results_exp7_context_framing_python_{m}.csv"),
}
TRUE = ("true", "1", "yes", "y")

def usable_set(dirn):
    s = set()
    for d in sorted(os.listdir(os.path.join(BASE, dirn))):
        p = os.path.join(BASE, dirn, d, "data.json")
        if not os.path.exists(p): continue
        j = json.load(open(p))
        if j.get("original_bug_line") is None: continue
        s.add((j.get("project", d.rsplit("_", 1)[0]), str(j.get("bug_id", d.rsplit("_", 1)[-1]))))
    return s

def rd(path):
    return list(csv.DictReader(open(path))) if os.path.exists(path) else None

def load_five(path, usable, raw):
    first, drop, dups = {}, 0, 0
    for r in rd(path) or []:
        raw[r["correct"]] += 1
        k = (r["project"], str(r["bug_id"]), r["tier"])
        if (k[0], k[1]) not in usable: drop += 1; continue
        if k in first: dups += 1; continue
        first[k] = r["correct"].strip().lower() in TRUE
    return first, drop, dups

def pct(a, b): return f"{100*a/b:.1f}%" if b else "n/a"

def mcnemar_p(b, c):
    n = b + c
    if n == 0: return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)

def to_int(x):
    try: return int(float(x))
    except Exception: return None

raw = collections.Counter()
for lang, cfg in LANGS.items():
    U = usable_set(cfg["data"])
    print("=" * 78); print(f"{lang.upper()}  usable bugs: {len(U)}"); print("=" * 78)
    data = {}
    for m in MODELS:
        first, drop, dups = load_five(os.path.join(BASE, cfg["res"], cfg["five"].format(m=m)), U, raw)
        data[m] = first
        print(f"{m}: unique usable rows {len(first)} | dropped (not usable) {drop} | duplicates removed {dups}")
    print("\n-- Stage 1 (baselines) and Stage 2 (gated), earliest row kept --")
    print(f"{'model':<28}{'T1 n':>6}{'T1 acc':>8}{'T2 n':>6}{'T2 acc':>8}{'bal':>8}{'T3 n':>6}{'T3 acc':>8}{'T3 excl':>8}{'T4 n':>6}{'T4 acc':>8}{'T4 excl':>8}")
    for m in MODELS:
        d = data[m]
        t1 = [v for k, v in d.items() if k[2] == "1"]; t2 = [v for k, v in d.items() if k[2] == "2"]
        c1, c2 = sum(t1), sum(t2)
        def gated(tier, pre):
            ev = [v for k, v in d.items() if k[2] == tier and d.get((k[0], k[1], pre)) is True]
            allr = [k for k in d if k[2] == tier]
            return len(ev), sum(ev), len(allr) - len(ev)
        n3, c3, x3 = gated("3", "1"); n5, c5, x5 = gated("5", "2")
        bal = (c1/len(t1) + c2/len(t2))/2*100 if t1 and t2 else float("nan")
        print(f"{m:<28}{len(t1):>6}{pct(c1,len(t1)):>8}{len(t2):>6}{pct(c2,len(t2)):>8}{bal:>7.1f}%{n3:>6}{pct(c3,n3):>8}{x3:>8}{n5:>6}{pct(c5,n5):>8}{x5:>8}")
    common = {(p, b) for (p, b) in U if all(((p, b, "1") in data[m] and (p, b, "2") in data[m]) for m in MODELS)}
    print(f"\n-- Common set: bugs all three models finished on T1 and T2 (n={len(common)}) --")
    for m in MODELS:
        a1 = [data[m][(p, b, "1")] for p, b in common]; a2 = [data[m][(p, b, "2")] for p, b in common]
        print(f"{m:<28} T1 {pct(sum(a1),len(a1)):>7}   T2 {pct(sum(a2),len(a2)):>7}   bal {((sum(a1)+sum(a2))/(2*len(a1))*100 if a1 else float('nan')):.1f}%")
    print("\n-- Probes (T2 = real buggy code; exact line vs old +-5; earliest row, usable bugs) --")
    for m in MODELS:
        P = {}
        for tag in ("p6", "p7"):
            rows = rd(os.path.join(BASE, cfg["res"], cfg[tag].format(m=m)))
            if rows is None: continue
            first = {}
            for r in rows:
                k = (r["project"], str(r["bug_id"]), r["tier"])
                if (k[0], k[1]) in U and k not in first: first[k] = r
            P[tag] = first
        for tag, name in (("p6", "Exp6 bug-ID"), ("p7", "Exp7 context")):
            if tag not in P: print(f"{m:<28}{name:<14} (no file)"); continue
            t2 = [r for k, r in P[tag].items() if k[2] == "2"]; t1 = [r for k, r in P[tag].items() if k[2] == "1"]
            ex = w5 = 0
            for r in t2:
                a, b = to_int(r["reported_line"]), to_int(r["actual_line"])
                if a is not None and b is not None:
                    ex += a == b; w5 += abs(a - b) <= 5
            fa = sum(to_int(r["reported_line"]) is not None for r in t1)
            print(f"{m:<28}{name:<14} T2 n={len(t2):>3} exact={ex:>3} ({pct(ex,len(t2))}) +-5={w5:>3} ({pct(w5,len(t2))}) | T1 n={len(t1):>3} gave a line={fa:>3} ({pct(fa,len(t1))})")
        if "p6" in P and "p7" in P:
            keys = [k for k in P["p6"] if k[2] == "2" and k in P["p7"]]
            def hit(r):
                a, b = to_int(r["reported_line"]), to_int(r["actual_line"]); return a is not None and b is not None and a == b
            b6 = sum(hit(P["p6"][k]) and not hit(P["p7"][k]) for k in keys)
            c7 = sum(hit(P["p7"][k]) and not hit(P["p6"][k]) for k in keys)
            print(f"{'':<28}paired T2 bugs={len(keys)}  Exp6-only exact={b6}  Exp7-only exact={c7}  McNemar p={mcnemar_p(b6, c7):.3f}")
    print()
print("raw 'correct' values seen:", dict(raw))
