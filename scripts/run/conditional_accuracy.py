"""
Implements the conditional scoring Gulzar described: a bug's Tier 3 result
only counts if the model already got Tier 1 right on that SAME bug, and a
bug's Tier 5 (his "Tier 4" -- disguised real bug) result only counts if the
model already got Tier 2 right on that same bug. This is a pure analysis
change -- it reads whatever tier data already exists in the results CSVs,
it does not require any new API calls.

Usage:
    python3 conditional_accuracy.py java glm-5.3-thinking
    python3 conditional_accuracy.py python deepseek-v4-flash-thinking
    python3 conditional_accuracy.py java all   # runs all 3 models
"""

import csv
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MODELS = ["glm-5.3-thinking", "deepseek-v4-flash-thinking", "gpt-oss-thinking"]


def load_results(language, model):
    if language == "python":
        path = os.path.join(BASE, "results/python", f"results_fivetier_python_{model}.csv")
    else:
        path = os.path.join(BASE, "results/java", f"results_fivetier_{model}.csv")

    if not os.path.exists(path):
        return None

    # key: (project, bug_id) -> {tier_str: row}
    by_bug = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            key = (row["project"], row["bug_id"])
            by_bug.setdefault(key, {})[row["tier"]] = row
    return by_bug


def analyze(language, model):
    by_bug = load_results(language, model)
    if by_bug is None:
        print(f"  No results file found for {model} ({language})")
        return

    # unconditional (plain) accuracy, tiers 1/2 -- these are always counted
    plain = {"1": [0, 0], "2": [0, 0]}
    # conditional: tier 3 only counts if this bug's tier 1 was correct;
    # tier 5 (Gulzar's "tier 4") only counts if this bug's tier 2 was correct
    cond = {"3": [0, 0], "5": [0, 0]}
    # also report how many bugs were ELIGIBLE vs how many got skipped by
    # the gating condition, so the denominator shift is visible
    eligible_but_wrong_baseline = {"3": 0, "5": 0}

    for key, tiers in by_bug.items():
        for t in ("1", "2"):
            if t in tiers:
                plain[t][1] += 1
                if tiers[t]["correct"] in ("True", "true"):
                    plain[t][0] += 1

        # tier 3 conditional on tier 1
        if "3" in tiers:
            if "1" in tiers and tiers["1"]["correct"] in ("True", "true"):
                cond["3"][1] += 1
                if tiers["3"]["correct"] in ("True", "true"):
                    cond["3"][0] += 1
            elif "1" in tiers:
                eligible_but_wrong_baseline["3"] += 1

        # tier 5 conditional on tier 2
        if "5" in tiers:
            if "2" in tiers and tiers["2"]["correct"] in ("True", "true"):
                cond["5"][1] += 1
                if tiers["5"]["correct"] in ("True", "true"):
                    cond["5"][0] += 1
            elif "2" in tiers:
                eligible_but_wrong_baseline["5"] += 1

    print(f"--- {model} ({language}) ---")
    for t, label in [("1", "Tier 1 (clean)"), ("2", "Tier 2 (real bug)")]:
        c, n = plain[t]
        pct = 100 * c / n if n else 0
        print(f"  {label}: {c}/{n} ({pct:.1f}%)  [unconditional]")

    for t, label, baseline in [("3", "Tier 3 (synthetic)", "1"), ("5", "Tier 5/'4' (disguised real bug)", "2")]:
        c, n = cond[t]
        pct = 100 * c / n if n else 0
        skipped = eligible_but_wrong_baseline[t]
        print(f"  {label}: {c}/{n} ({pct:.1f}%)  [conditional on Tier {baseline} correct; "
              f"{skipped} bugs excluded for failing Tier {baseline}]")
    print()


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 conditional_accuracy.py <java|python> <model_key|all>")
        sys.exit(1)

    language = sys.argv[1]
    model_arg = sys.argv[2]

    models = MODELS if model_arg == "all" else [model_arg]
    for model in models:
        analyze(language, model)


if __name__ == "__main__":
    main()

