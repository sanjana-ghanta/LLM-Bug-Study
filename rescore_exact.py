import csv, os
from collections import Counter

PROBES = {
    "Bug-ID Recall": "results/java/results_exp6_bugid_recall_{m}.csv",
    "Context Framing": "results/java/results_exp7_context_framing_{m}.csv",
}
MODELS = ["glm-5.3-thinking", "deepseek-v4-flash-thinking", "gpt-oss-thinking"]

def to_int(x):
    try:
        return int(float(str(x).strip()))
    except Exception:
        return None

for probe, pat in PROBES.items():
    for m in MODELS:
        path = pat.format(m=m)
        if not os.path.exists(path):
            continue
        latest = {}
        with open(path, newline="") as f:
            for r in csv.DictReader(f):
                latest[(r["project"], r["bug_id"], str(r["tier"]).strip())] = r
        t1 = [r for k, r in latest.items() if k[2][-1:] == "1"]
        t2 = [r for k, r in latest.items() if k[2][-1:] == "2"]
        print(f"\n== {probe} | {m} ==")
        print("T1 rows:", len(t1), dict(Counter(r["classification"] for r in t1)))
        print("T2 rows:", len(t2), dict(Counter(r["classification"] for r in t2)))
        with_line = [r for r in t2 if to_int(r["reported_line"]) is not None and to_int(r["actual_line"]) is not None]
        exact = sum(1 for r in with_line if to_int(r["reported_line"]) == to_int(r["actual_line"]))
        near = sum(1 for r in with_line if abs(to_int(r["reported_line"]) - to_int(r["actual_line"])) <= 5)
        print(f"T2 with a reported line: {len(with_line)}")
        print(f"T2 exact match: {exact}   within +/-5: {near}")
