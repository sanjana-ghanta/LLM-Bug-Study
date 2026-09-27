"""
Audits the EXISTING results.csv (original Claude-only Experiment 1 run)
against each bug's known line-number metadata, to determine exactly how
many results were affected by the old truncate_code(max_lines=80) bug --
i.e. how many bugs sat past line 80 in a file the model was only ever
shown the first 80 lines of.

Does not modify anything -- read-only audit, prints a summary and writes
a detailed per-row CSV so you can see exactly which specific results are
in question.
"""

import csv
import json
import os

BASE = os.path.expanduser("~/llm-bug-study/experiment")
RESULTS_CSV = os.path.join(BASE, "results/java/results.csv")
BUGS_DIR = os.path.join(BASE, "data/bugs")
OUT_CSV = os.path.join(BASE, "results/java/results_truncation_audit.csv")

OLD_TRUNCATION_CUTOFF = 80  # the original truncate_code(max_lines=80)

# which data.json field holds the relevant line number for each tier
LINE_FIELD_BY_TIER = {
    "1": "original_bug_line",   # patched code -- same region as tier 2
    "2": "original_bug_line",
    "3": "tier3_mutation_line",
    "4": "tier4_mutation_line",
    "5": None,                  # no known post-rewrite line number
}


def main():
    if not os.path.exists(RESULTS_CSV):
        print(f"Could not find {RESULTS_CSV}")
        return

    with open(RESULTS_CSV) as f:
        rows = list(csv.DictReader(f))

    print(f"Auditing {len(rows)} existing rows from results.csv...\n")

    audit_rows = []
    data_json_cache = {}

    for row in rows:
        project = row["project"]
        bug_id = row["bug_id"]
        tier = row["tier"]

        cache_key = f"{project}_{bug_id}"
        if cache_key not in data_json_cache:
            data_path = os.path.join(BUGS_DIR, cache_key, "data.json")
            if os.path.exists(data_path):
                with open(data_path) as f:
                    data_json_cache[cache_key] = json.load(f)
            else:
                data_json_cache[cache_key] = None
        data = data_json_cache[cache_key]

        if data is None:
            status = "NO_DATA_JSON"
            line_number = None
        else:
            line_field = LINE_FIELD_BY_TIER.get(tier)
            if line_field is None:
                status = "UNKNOWN_LINE"  # tier 5 -- can't verify
                line_number = None
            else:
                line_number = data.get(line_field)
                if line_number is None:
                    status = "NO_LINE_DATA"
                elif line_number > OLD_TRUNCATION_CUTOFF:
                    status = "BLIND"       # bug was past line 80 -- never shown
                else:
                    status = "VISIBLE"     # bug was within the first 80 lines

        audit_rows.append({
            "project": project,
            "bug_id": bug_id,
            "tier": tier,
            "expected": row["expected"],
            "verdict": row["verdict"],
            "correct": row["correct"],
            "line_number": line_number,
            "status": status,
        })

    # write detailed audit
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    with open(OUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(audit_rows[0].keys()))
        writer.writeheader()
        writer.writerows(audit_rows)

    # summary
    from collections import Counter
    status_counts = Counter(r["status"] for r in audit_rows)
    print("=== Overall status breakdown ===")
    for status, count in status_counts.most_common():
        print(f"  {status}: {count} ({100*count/len(audit_rows):.1f}%)")

    # the number that actually matters: BLIND rows where the model got it
    # WRONG -- these are the ones genuinely compromised by truncation and
    # worth rerunning. A BLIND row that happened to be marked correct isn't
    # actually a problem (rare, but possible if e.g. tier 1's "NO BUG"
    # expectation was met regardless of what was shown).
    blind_rows = [r for r in audit_rows if r["status"] == "BLIND"]
    blind_and_wrong = [r for r in blind_rows if r["correct"] in ("False", False)]
    blind_and_right = [r for r in blind_rows if r["correct"] in ("True", True)]

    print(f"\n=== Of the {len(blind_rows)} BLIND rows (bug past line {OLD_TRUNCATION_CUTOFF}) ===")
    print(f"  Marked INCORRECT (genuinely compromised, worth rerunning): {len(blind_and_wrong)}")
    print(f"  Marked CORRECT despite not seeing the bug (unaffected in practice): {len(blind_and_right)}")

    print(f"\n=== Bottom line ===")
    print(f"  {len(blind_and_wrong)} / {len(audit_rows)} total results "
          f"({100*len(blind_and_wrong)/len(audit_rows):.1f}%) are results where "
          f"the model was never shown the actual bug AND got the verdict wrong.")
    print(f"  These are the ones that need to be rerun with the fixed script.")
    print(f"\nFull per-row detail saved to: {OUT_CSV}")


if __name__ == "__main__":
    main()

