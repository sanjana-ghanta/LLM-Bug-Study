"""
Finds every bug a given model got WRONG on Tier 2 (the real, undisguised
bug) -- this is the target set for the two follow-up experiments
(Benchmark-Context Framing, Bug-ID Recall), which only make sense to run
on bugs the model failed to catch from the code alone.

Usage:
    python3 find_tier2_misses.py java glm-5.3-thinking
    python3 find_tier2_misses.py python deepseek-v4-flash-thinking
"""

import csv
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def find_misses(language, model):
    if language == "python":
        path = os.path.join(BASE, "results/python", f"results_fivetier_python_{model}.csv")
    else:
        path = os.path.join(BASE, "results/java", f"results_fivetier_{model}.csv")

    if not os.path.exists(path):
        print(f"No results file found for {model} ({language})")
        return []

    misses = []
    with open(path) as f:
        for row in csv.DictReader(f):
            if row["tier"] == "2" and row["correct"] not in ("True", "true"):
                misses.append((row["project"], row["bug_id"]))

    return misses


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 find_tier2_misses.py <java|python> <model_key>")
        sys.exit(1)

    language = sys.argv[1]
    model = sys.argv[2]

    misses = find_misses(language, model)
    print(f"{model} ({language}): {len(misses)} bugs missed on Tier 2")

    out_path = os.path.join(BASE, f"tier2_misses_{language}_{model}.txt")
    with open(out_path, "w") as f:
        for project, bug_id in misses:
            f.write(f"{project}_{bug_id}\n")
    print(f"Saved list to {out_path}")


if __name__ == "__main__":
    main()

