"""
The v2 coverage script also picked the FIRST occurrence of duplicated text,
same flaw as the original apply_fix_to_file(). This recomputes claude_line
coverage for the 8 duplicated bugs using the closest-to-reported occurrence
(the same choice reverify_duplicated_bugs.py already made and printed as
chosen_occurrence_line), then patches just those 8 rows in
results_actuallinecoverage_v2.csv. The other 42 rows are untouched.
"""

import xml.etree.ElementTree as ET
import subprocess
import os
import csv
import shutil

BASE = os.path.expanduser("~/llm-bug-study/experiment")
COVERAGE_CSV = os.path.join(BASE, "results/java/results_actuallinecoverage_v2.csv")
REVERIFY_CSV = os.path.join(BASE, "results/java/results_duplicate_reverify.csv")


def checkout_bug(project, bug_id, target_dir):
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir)
    result = subprocess.run(
        ['defects4j', 'checkout', '-p', project, '-v', f'{bug_id}b', '-w', target_dir],
        capture_output=True, text=True, timeout=120
    )
    return os.path.exists(target_dir)


def run_coverage(checkout_dir):
    subprocess.run(
        ['defects4j', 'coverage', '-w', checkout_dir],
        capture_output=True, text=True, timeout=600
    )
    xml_path = os.path.join(checkout_dir, 'coverage.xml')
    return xml_path if os.path.exists(xml_path) else None


def get_line_hits(xml_path, filename_contains, lineno):
    if not xml_path or not os.path.exists(xml_path) or lineno is None:
        return None
    tree = ET.parse(xml_path)
    root = tree.getroot()
    for cls in root.findall('.//class'):
        if filename_contains in cls.get('filename', ''):
            for line in cls.findall('.//line'):
                if int(line.get('number')) == lineno:
                    return int(line.get('hits', 0))
    return None


with open(REVERIFY_CSV) as f:
    reverify_rows = {(r['project'], r['bug_id']): r for r in csv.DictReader(f)}

backup_path = COVERAGE_CSV + ".before_duplicate_fix.bak"
shutil.copy(COVERAGE_CSV, backup_path)
print(f"Backup saved to {backup_path}")

with open(COVERAGE_CSV) as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    coverage_rows = list(reader)

extra_fields = ['corrected_for_duplicate_line']
for field in extra_fields:
    if field not in fieldnames:
        fieldnames.append(field)

for row in coverage_rows:
    key = (row['project'], row['bug_id'])
    if key not in reverify_rows:
        row.setdefault('corrected_for_duplicate_line', 'False')
        continue

    rv = reverify_rows[key]
    correct_line = int(rv['chosen_occurrence_line'])
    filename = row['file']

    print(f"\n{key}: recomputing coverage at corrected line {correct_line} "
          f"(was checking line {row['claude_line_verified']})")

    project, bug_id = key
    tmp_dir = f"/tmp/{project}_{bug_id}_covfix"
    if not checkout_bug(project, bug_id, tmp_dir):
        print("  Checkout failed, skipping")
        continue

    xml_path = run_coverage(tmp_dir)
    if not xml_path:
        print("  Coverage failed, skipping")
        shutil.rmtree(tmp_dir, ignore_errors=True)
        continue

    new_hits = get_line_hits(xml_path, filename, correct_line)
    new_covered = new_hits is not None and new_hits > 0

    print(f"  New result: line {correct_line}, {new_hits} hits, covered={new_covered}")

    row['claude_line_verified'] = str(correct_line)
    row['claude_hits'] = str(new_hits)
    row['claude_covered'] = str(new_covered)
    row['corrected_for_duplicate_line'] = 'True'

    shutil.rmtree(tmp_dir, ignore_errors=True)

with open(COVERAGE_CSV, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(coverage_rows)

print(f"\nDone. Updated {COVERAGE_CSV}")
print(f"Original preserved at {backup_path}")

