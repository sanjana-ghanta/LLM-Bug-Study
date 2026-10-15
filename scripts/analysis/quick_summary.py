#!/usr/bin/env python3
"""Per-tier accuracy for one results CSV. T3 scored where T1 was correct, T4 where T2 was correct."""
import csv, sys
rows = list(csv.DictReader(open(sys.argv[1], newline="")))
res = {}
for r in rows:
    res.setdefault((r["project"], r["bug_id"]), {}).setdefault(r["tier"], r["correct"] == "True")
def acc(tier, gate=None):
    n = c = 0
    for t in res.values():
        if tier in t and (gate is None or t.get(gate)):
            n += 1; c += t[tier]
    return f"{c}/{n} ({100*c/n:.0f}%)" if n else "0/0"
print("T1 (clean)      ", acc("1"))
print("T2 (real bug)   ", acc("2"))
print("T3 (mutation)   ", acc("3", "1"), " [where T1 correct]")
print("T4 (disguised)  ", acc("5", "2"), " [where T2 correct]")
