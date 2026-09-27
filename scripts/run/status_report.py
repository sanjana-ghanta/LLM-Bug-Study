"""
Full status report across the whole pipeline: which projects are actually
extracted/usable, which models have finished tier5 generation for which
bugs, and which model x project combinations have completed detection.

Entirely read-only -- doesn't run or change anything, just reports.

Usage:
    python3 status_report.py
"""

import json
import os
import csv
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BUGS_DIR = os.path.join(BASE, "data/bugs")
RESULTS_DIR = os.path.join(BASE, "results/java")

MODELS = ["glm-5.3-thinking", "deepseek-v4-flash-thinking", "gpt-oss-thinking"]

TIERS = ["1", "2", "3", "4", "5"]


def main():
    if not os.path.exists(BUGS_DIR):
        print(f"BUGS_DIR not found: {BUGS_DIR}")
        return

    # --- Section 1: extraction / line-detection / SPM injection completeness ---
    usable = defaultdict(int)
    unusable = defaultdict(int)
    no_spm = defaultdict(int)
    tier5_present = defaultdict(lambda: defaultdict(int))
    tier5_missing = defaultdict(lambda: defaultdict(int))

    all_bug_dirs = sorted(os.listdir(BUGS_DIR))
    for bug_dir in all_bug_dirs:
        data_path = os.path.join(BUGS_DIR, bug_dir, "data.json")
        if not os.path.exists(data_path):
            continue
        with open(data_path) as f:
            data = json.load(f)
        project = data.get("project", bug_dir.split("_")[0])

        if data.get("original_bug_line") is not None:
            usable[project] += 1
        else:
            unusable[project] += 1
            continue  # can't check SPM/tier5 meaningfully without a line

        if data.get("tier3_code") is None:
            no_spm[project] += 1

        by_model = data.get("tier5_code_by_model", {})
        for model in MODELS:
            if model in by_model:
                tier5_present[model][project] += 1
            else:
                tier5_missing[model][project] += 1

    all_projects = sorted(set(usable) | set(unusable))

    print("=" * 70)
    print("SECTION 1: Extraction / line-detection completeness")
    print("=" * 70)
    print(f"{'Project':<16}{'Usable':<10}{'Unusable':<10}{'No SPM':<10}")
    for p in all_projects:
        print(f"{p:<16}{usable[p]:<10}{unusable[p]:<10}{no_spm[p]:<10}")
    print(f"\nTOTAL usable bugs across all projects: {sum(usable.values())}")

    print()
    print("=" * 70)
    print("SECTION 2: Tier5 generation completeness per model")
    print("=" * 70)
    for model in MODELS:
        print(f"\n--- {model} ---")
        for p in all_projects:
            present = tier5_present[model][p]
            missing = tier5_missing[model][p]
            if present + missing == 0:
                continue
            flag = "  <-- INCOMPLETE" if missing > 0 else ""
            print(f"  {p:<16}present={present:<6}missing={missing:<6}{flag}")

    # --- Section 3: detection completeness per model ---
    print()
    print("=" * 70)
    print("SECTION 3: Detection run completeness per model")
    print("=" * 70)
    for model in MODELS:
        csv_path = os.path.join(RESULTS_DIR, f"results_fivetier_{model}.csv")
        if not os.path.exists(csv_path):
            print(f"\n--- {model}: NO RESULTS FILE YET ---")
            continue
        with open(csv_path) as f:
            rows = list(csv.DictReader(f))
        by_project_tier = defaultdict(lambda: defaultdict(int))
        for r in rows:
            by_project_tier[r["project"]][r["tier"]] += 1

        print(f"\n--- {model} ({len(rows)} total rows) ---")
        for p in sorted(by_project_tier.keys()):
            tier_counts = by_project_tier[p]
            expected = usable.get(p, 0)
            summary = ", ".join(f"T{t}={tier_counts.get(t, 0)}" for t in TIERS)
            print(f"  {p:<16}expected~{expected:<6}{summary}")

    print()
    print("=" * 70)
    print("Done. 'Usable' bugs (Section 1) is the real target count per")
    print("project -- compare Section 3's tier counts against it to see")
    print("how much detection work remains per model/project.")
    print("=" * 70)


if __name__ == "__main__":
    main()

