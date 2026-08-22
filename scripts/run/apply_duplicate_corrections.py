"""
Applies the corrected re-verification results for Chart_1 and Chart_7 to
results_testflip.csv. These two were originally measured against the wrong
copy of duplicated code text; the reverify script confirmed that applying
the fix at the correct occurrence (closest to Claude's reported line, which
also happened to match the real documented bug line for these two) produces
a genuine test-flip for both.

Only these 2 rows are touched. The other 48 are left exactly as they were.
A backup of the original file is saved first.
"""

import csv
import os
import shutil

BASE = os.path.expanduser("~/llm-bug-study/experiment")
TESTFLIP_CSV = os.path.join(BASE, "results/java/results_testflip.csv")
REVERIFY_CSV = os.path.join(BASE, "results/java/results_duplicate_reverify.csv")

CORRECTIONS = [("Chart", "1"), ("Chart", "7")]

# backup original before touching anything
backup_path = TESTFLIP_CSV + ".before_duplicate_fix.bak"
shutil.copy(TESTFLIP_CSV, backup_path)
print(f"Backup of original saved to: {backup_path}")

with open(REVERIFY_CSV) as f:
    reverify_rows = {(r['project'], r['bug_id']): r for r in csv.DictReader(f)}

with open(TESTFLIP_CSV) as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    testflip_rows = list(reader)

# add two new columns if not already present, for transparency
extra_fields = ['corrected_for_duplicate_line', 'correction_note']
for field in extra_fields:
    if field not in fieldnames:
        fieldnames.append(field)

updated_count = 0
for row in testflip_rows:
    key = (row['project'], row['bug_id'])
    if key not in dict.fromkeys(CORRECTIONS):
        row.setdefault('corrected_for_duplicate_line', 'False')
        row.setdefault('correction_note', '')
        continue

    if key not in reverify_rows:
        print(f"WARNING: {key} marked for correction but not found in reverify results, skipping")
        continue

    rv = reverify_rows[key]
    old_summary = f"n_before={row['n_before']} n_after={row['n_after']} clean_pass={row.get('clean_pass')}"

    row['n_before'] = rv['n_before']
    row['n_after'] = rv['n_after']
    row['flipped_to_pass'] = rv['flipped_to_pass']
    row['flipped_to_fail'] = rv['flipped_to_fail']
    # n_after was 0 for both corrected bugs, so nothing remains still-failing
    row['still_failing'] = ''
    row['n_flipped_to_pass'] = str(len(rv['flipped_to_pass'].split(';'))) if rv['flipped_to_pass'] else '0'
    row['n_flipped_to_fail'] = str(len(rv['flipped_to_fail'].split(';'))) if rv['flipped_to_fail'] else '0'
    row['any_flip_to_pass'] = rv['any_flip_to_pass']
    row['clean_pass'] = str(rv['n_after'] == '0')
    row['corrected_for_duplicate_line'] = 'True'
    row['correction_note'] = (
        f"Original fix applied at wrong occurrence of duplicated text. "
        f"Reapplied at line {rv['chosen_occurrence_line']} (matches actual documented line). "
        f"Was: {old_summary}"
    )

    print(f"Updated {key}: {old_summary} -> n_before={rv['n_before']} n_after={rv['n_after']} "
          f"any_flip_to_pass={rv['any_flip_to_pass']}")
    updated_count += 1

with open(TESTFLIP_CSV, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(testflip_rows)

print(f"\nDone. {updated_count} row(s) corrected in {TESTFLIP_CSV}")
print(f"Original (uncorrected) version preserved at {backup_path}")

