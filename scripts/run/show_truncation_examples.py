"""
Reconstructs exactly what code was sent to Claude (using the OLD, buggy
truncate_code(max_lines=80) logic) for a sample of the confirmed-compromised
rows from results_truncation_audit.csv, and shows it side-by-side with
Claude's actual stored response -- to see the causal story directly rather
than just trust the audit numbers.

Read-only. No API calls.
"""

import csv
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RESULTS_CSV = os.path.join(BASE, "results/java/results.csv")
AUDIT_CSV = os.path.join(BASE, "results/java/results_truncation_audit.csv")
BUGS_DIR = os.path.join(BASE, "data/bugs")

OLD_TRUNCATION_CUTOFF = 80
N_EXAMPLES = 5

CODE_KEY_BY_TIER = {
    "1": "patched_code",
    "2": "buggy_code",
    "3": "tier3_code",
    "4": "tier4_code",
    "5": "tier5_code",
}


def old_truncate_code(code, max_lines=80):
    lines = code.splitlines()
    if len(lines) > max_lines:
        return "\n".join(lines[:max_lines]) + "\n... (truncated)"
    return code


def main():
    with open(AUDIT_CSV) as f:
        audit_rows = list(csv.DictReader(f))
    with open(RESULTS_CSV) as f:
        results_rows = list(csv.DictReader(f))

    # index results by (project, bug_id, tier) to look up the stored response
    results_index = {(r["project"], r["bug_id"], r["tier"]): r for r in results_rows}

    compromised = [r for r in audit_rows if r["status"] == "BLIND" and r["correct"] in ("False", "false")]

    print(f"Found {len(compromised)} compromised rows total. Showing {min(N_EXAMPLES, len(compromised))} examples:\n")

    for row in compromised[:N_EXAMPLES]:
        project, bug_id, tier = row["project"], row["bug_id"], row["tier"]
        line_number = row["line_number"]

        data_path = os.path.join(BUGS_DIR, f"{project}_{bug_id}", "data.json")
        with open(data_path) as f:
            data = json.load(f)

        code_key = CODE_KEY_BY_TIER[tier]
        full_code = data.get(code_key, "")
        total_lines = len(full_code.splitlines())
        old_sent = old_truncate_code(full_code, OLD_TRUNCATION_CUTOFF)

        stored_result = results_index.get((project, bug_id, tier))

        print(f"{'='*70}")
        print(f"=== {project}_{bug_id}, tier {tier} ===")
        print(f"{'='*70}")
        print(f"Real bug line: {line_number}  |  File length: {total_lines} lines  |  "
              f"Old truncation only sent lines 1-{OLD_TRUNCATION_CUTOFF}")
        print()
        print(f"--- Last ~200 chars of what Claude was ACTUALLY shown (old truncation) ---")
        print(old_sent[-200:])
        print()
        if stored_result:
            print(f"--- Claude's ACTUAL stored response ---")
            print(f"Expected: {stored_result['expected']}  |  Verdict: {stored_result['verdict']}  |  "
                  f"Correct: {stored_result['correct']}")
            print(f"Response: {stored_result['response']}")
        else:
            print("(No matching row found in results.csv)")
        print()

    remaining = max(0, len(compromised) - N_EXAMPLES)
    print(f"\n{remaining} more compromised rows not shown here "
          f"(full list in results_truncation_audit.csv, filtered to status=BLIND and correct=False).")


if __name__ == "__main__":
    main()

