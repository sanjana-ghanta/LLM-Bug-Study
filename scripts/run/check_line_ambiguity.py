"""
Disambiguation check: for each of the 50 bugs, count how many times
original_code's exact text appears in the checked-out source file.

- count == 1: text is unique. No ambiguity -- Claude's self-reported line
  number was just wrong, but the fix landed on the one and only correct
  spot. Not a real problem.
- count > 1: text is genuinely duplicated. apply_fix_to_file() always edits
  the FIRST occurrence -- this could be the wrong one. Worth flagging
  per-bug for manual review.
- count == 0: text isn't found at all (shouldn't happen if fix_applied was
  True, but worth knowing if it does).
"""

import os
import csv
import json
import subprocess
import shutil

BASE = os.path.expanduser("~/llm-bug-study/experiment")
BUGS_DIR = os.path.join(BASE, "data/bugs")
OUT_CSV = os.path.join(BASE, "results/java/results_ambiguity_check.csv")

SOURCES = [
    ("Chart", os.path.join(BASE, "results/java/results_v9_testfix.csv"), ["source", "src", "src/main/java", ""]),
    ("Lang", os.path.join(BASE, "results/java/results_v9_testfix_lang.csv"), ["src/main/java", "src", "source", ""]),
    ("Math", os.path.join(BASE, "results/java/results_v9_testfix_math.csv"), ["src/main/java", "src", "source", ""]),
]


def checkout_bug(project, bug_id, target_dir):
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir)
    result = subprocess.run(
        ['defects4j', 'checkout', '-p', project, '-v', f'{bug_id}b', '-w', target_dir],
        capture_output=True, text=True, timeout=120
    )
    return os.path.exists(target_dir)


def find_source_file(tmp_dir, file_path, src_candidates):
    for src in src_candidates:
        candidate = os.path.join(tmp_dir, src, file_path) if src else os.path.join(tmp_dir, file_path)
        if os.path.exists(candidate):
            return candidate
    return None


fields = ['project', 'bug_id', 'claude_line_reported', 'occurrence_count', 'matching_line_numbers', 'status']

completed = set()
if os.path.exists(OUT_CSV):
    with open(OUT_CSV) as f:
        for row in csv.DictReader(f):
            completed.add((row['project'], row['bug_id']))

print(f"Already completed: {len(completed)}")

with open(OUT_CSV, 'a', newline='') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=fields)
    if len(completed) == 0:
        writer.writeheader()

    for project, path, src_candidates in SOURCES:
        if not os.path.exists(path):
            continue
        with open(path) as f:
            rows = list(csv.DictReader(f))

        print(f"\n=== {project}: {len(rows)} bugs ===")

        for row in rows:
            bug_id = row['bug_id']
            if (project, bug_id) in completed:
                continue

            original_code = row.get('original_code', '')
            claude_line_reported = row.get('claude_line', '')
            if not original_code:
                continue

            data_path = os.path.join(BUGS_DIR, f"{project}_{bug_id}", "data.json")
            if not os.path.exists(data_path):
                continue
            with open(data_path) as f:
                data = json.load(f)
            file_path = data.get('file_path', '')

            tmp_dir = f"/tmp/{project}_{bug_id}_ambig"
            if not checkout_bug(project, bug_id, tmp_dir):
                print(f"  {project}_{bug_id}: checkout failed")
                continue

            full_path = find_source_file(tmp_dir, file_path, src_candidates)
            if not full_path:
                print(f"  {project}_{bug_id}: source file not found")
                shutil.rmtree(tmp_dir, ignore_errors=True)
                continue

            with open(full_path) as f:
                lines = f.readlines()
            matches = [i + 1 for i, line in enumerate(lines) if line.strip() == original_code.strip()]

            if len(matches) == 0:
                status = "NOT_FOUND"
            elif len(matches) == 1:
                status = "UNIQUE"
            else:
                status = "DUPLICATED"

            print(f"  {project}_{bug_id}: '{original_code.strip()[:60]}...' "
                  f"-> {len(matches)} occurrence(s) at lines {matches} [{status}]")

            writer.writerow({
                'project': project,
                'bug_id': bug_id,
                'claude_line_reported': claude_line_reported,
                'occurrence_count': len(matches),
                'matching_line_numbers': ';'.join(str(m) for m in matches),
                'status': status,
            })
            csvfile.flush()
            shutil.rmtree(tmp_dir, ignore_errors=True)

print(f"\nDone! Results saved to {OUT_CSV}")

