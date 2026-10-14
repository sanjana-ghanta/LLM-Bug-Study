import csv, glob, os, collections
for exp, pat in [("Exp6 (bug ID given)", "results/java/results_exp6_bugid_recall_*.csv"),
                 ("Exp7 (benchmark context only)", "results/java/results_exp7_context_framing_*.csv")]:
    print("=== " + exp + " ===")
    for path in sorted(glob.glob(pat)):
        model = os.path.basename(path)[:-4].split("_")[-1]
        c = collections.defaultdict(collections.Counter)
        with open(path, newline="") as f:
            for r in csv.DictReader(f):
                c[r["tier"]][r["classification"]] += 1
        t1, t2 = c["1"], c["2"]
        n1, n2 = sum(t1.values()), sum(t2.values())
        p1 = 100.0 * t1["pattern_matched_clean"] / n1 if n1 else 0
        p2 = 100.0 * t2["correct"] / n2 if n2 else 0
        print(model)
        print("  Tier 1 clean: false-positive %d/%d (%.1f%%)  %s" % (t1["pattern_matched_clean"], n1, p1, dict(t1)))
        print("  Tier 2 bug:   recovered      %d/%d (%.1f%%)  %s" % (t2["correct"], n2, p2, dict(t2)))
