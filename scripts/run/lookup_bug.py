"""
Quick lookup: print the failing-test breakdown for any bug from
results_testflip.csv. Usage:

    python3 lookup_bug.py Chart_26
    python3 lookup_bug.py Math_16
"""
import csv
import sys
import os

CSV_PATH = os.path.expanduser("~/llm-bug-study/experiment/results/java/results_testflip.csv")

if len(sys.argv) < 2:
    print("Usage: python3 lookup_bug.py <Project_BugID>   e.g. Chart_26")
    sys.exit(1)

target = sys.argv[1]
project, bug_id = target.rsplit("_", 1)

with open(CSV_PATH) as f:
    rows = list(csv.DictReader(f))

row = next((r for r in rows if r['project'] == project and r['bug_id'] == bug_id), None)

if row is None:
    print(f"No entry found for {target}")
    sys.exit(1)

def show(label, field):
    val = row[field]
    tests = val.split(";") if val else []
    print(f"\n{label} ({len(tests)}):")
    for t in tests:
        print(f"  - {t}")

print(f"=== {project}_{bug_id} ===")
print(f"actual_line: {row['actual_line']}   claude_line: {row['claude_line']}")
print(f"n_before: {row['n_before']}   n_after: {row['n_after']}")
print(f"clean_pass: {row['clean_pass']}   any_flip_to_pass: {row['any_flip_to_pass']}")

show("FLIPPED TO PASS (fixed by Claude's edit)", "flipped_to_pass")
show("FLIPPED TO FAIL (regressions introduced)", "flipped_to_fail")
show("STILL FAILING (unaffected)", "still_failing")

