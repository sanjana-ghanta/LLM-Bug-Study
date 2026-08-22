"""
Re-verification for the 8 bugs flagged DUPLICATED by check_line_ambiguity.py.

For each: re-derive which occurrence is closest to Claude's reported line,
check whether that occurrence is actually the real documented bug line,
then re-apply the fix there and re-measure test outcomes.

This does NOT touch the other 42 bugs -- they were already fine.
"""

import subprocess
import os
import csv
import json
import shutil
import re

BASE = os.path.expanduser("~/llm-bug-study/experiment")
BUGS_DIR = os.path.join(BASE, "data/bugs")
OUT_CSV = os.path.join(BASE, "results/java/results_duplicate_reverify.csv")

SOURCES = {
    "Chart": (os.path.join(BASE, "results/java/results_v9_testfix.csv"), ["source", "src", "src/main/java", ""]),
    "Lang": (os.path.join(BASE, "results/java/results_v9_testfix_lang.csv"), ["src/main/java", "src", "source", ""]),
    "Math": (os.path.join(BASE, "results/java/results_v9_testfix_math.csv"), ["src/main/java", "src", "source", ""]),
}

DUPLICATED_BUGS = [
    ("Chart", "16"), ("Chart", "8"), ("Chart", "7"), ("Chart", "6"), ("Chart", "1"),
    ("Lang", "3"), ("Lang", "7"), ("Math", "10"),
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


def apply_fix_closest(full_file_path, original_line, fixed_line, reported_line):
    with open(full_file_path) as f:
        lines = f.readlines()
    match_indices = [i for i, line in enumerate(lines) if line.strip() == original_line.strip()]
    if not match_indices:
        return False, None
    chosen_idx = min(match_indices, key=lambda idx: abs((idx + 1) - reported_line))
    indent = len(lines[chosen_idx]) - len(lines[chosen_idx].lstrip())
    lines[chosen_idx] = " " * indent + fixed_line.strip() + "\n"
    with open(full_file_path, "w") as f:
        f.writelines(lines)
    return True, chosen_idx + 1  # 1-indexed


def capture_failing_tests(checkout_dir):
    result = subprocess.run(
        ['defects4j', 'test', '-w', checkout_dir],
        capture_output=True, text=True, timeout=300
    )
    output = result.stdout + result.stderr
    names = set()
    failing_tests_path = os.path.join(checkout_dir, 'failing_tests')
    if os.path.exists(failing_tests_path):
        with open(failing_tests_path) as f:
            content = f.read()
        names = set(re.findall(r'--- (\S+)', content))
    if not names:
        names = set(re.findall(r'^\s*-\s+(\S+)', output, re.MULTILINE))
    return names


fields = [
    'project', 'bug_id', 'actual_line', 'claude_line_reported',
    'chosen_occurrence_line', 'matches_actual_line',
    'n_before', 'n_after', 'flipped_to_pass', 'flipped_to_fail', 'any_flip_to_pass',
]

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

    for project, bug_id in DUPLICATED_BUGS:
        if (project, bug_id) in completed:
            print(f"Skipping {project}_{bug_id} (already done)")
            continue

        results_csv, src_candidates = SOURCES[project]
        with open(results_csv) as f:
            rows = list(csv.DictReader(f))
        row = next(r for r in rows if r['bug_id'] == bug_id)

        actual_line = int(row['actual_line'])
        claude_line_reported = int(row['claude_line'])
        original_code = row['original_code']
        fixed_code = row['fixed_code']

        data_path = os.path.join(BUGS_DIR, f"{project}_{bug_id}", "data.json")
        with open(data_path) as f:
            data = json.load(f)
        file_path = data.get('file_path', '')

        print(f"\n=== {project}_{bug_id} | actual_line={actual_line} claude_reported={claude_line_reported} ===")

        tmp_dir = f"/tmp/{project}_{bug_id}_reverify"
        print("  Checking out...")
        if not checkout_bug(project, bug_id, tmp_dir):
            print("  Checkout failed, skipping")
            continue

        full_path = find_source_file(tmp_dir, file_path, src_candidates)
        if not full_path:
            print("  Source file not found, skipping")
            shutil.rmtree(tmp_dir, ignore_errors=True)
            continue

        print("  Capturing failing tests BEFORE fix...")
        before_tests = capture_failing_tests(tmp_dir)
        print(f"  Failing before: {len(before_tests)}")

        applied, chosen_line = apply_fix_closest(full_path, original_code, fixed_code, claude_line_reported)
        if not applied:
            print("  Could not apply fix, skipping")
            shutil.rmtree(tmp_dir, ignore_errors=True)
            continue

        matches_actual = (chosen_line == actual_line)
        print(f"  Applied fix at line {chosen_line} (closest to reported {claude_line_reported}) "
              f"-- {'MATCHES actual documented line!' if matches_actual else 'still does NOT match actual line ' + str(actual_line)}")

        print("  Capturing failing tests AFTER fix...")
        after_tests = capture_failing_tests(tmp_dir)
        print(f"  Failing after: {len(after_tests)}")

        flipped_to_pass = before_tests - after_tests
        flipped_to_fail = after_tests - before_tests

        print(f"  Flipped to pass: {len(flipped_to_pass)} | Flipped to fail: {len(flipped_to_fail)}")

        writer.writerow({
            'project': project,
            'bug_id': bug_id,
            'actual_line': actual_line,
            'claude_line_reported': claude_line_reported,
            'chosen_occurrence_line': chosen_line,
            'matches_actual_line': matches_actual,
            'n_before': len(before_tests),
            'n_after': len(after_tests),
            'flipped_to_pass': ";".join(sorted(flipped_to_pass)),
            'flipped_to_fail': ";".join(sorted(flipped_to_fail)),
            'any_flip_to_pass': len(flipped_to_pass) > 0,
        })
        csvfile.flush()
        shutil.rmtree(tmp_dir, ignore_errors=True)

print(f"\nDone! Results saved to {OUT_CSV}")

