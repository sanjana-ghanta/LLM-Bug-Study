"""
Follow-up flakiness check: baseline (no fix) was confirmed deterministic for
Chart_26 and Math_16 (5/5 identical runs each). This checks the *post-fix*
state instead, applying the same fix from results_v9_testfix*.csv and
running defects4j test 5 times on that fixed checkout, without re-checking
out between runs.
"""

import os
import csv
import re
import shutil
import subprocess

N_RUNS = 5

BASE = os.path.expanduser("~/llm-bug-study/experiment")
BUGS_TO_CHECK = [
    ("Chart", "26", os.path.join(BASE, "results/java/results_v9_testfix.csv")),
    ("Math", "16", os.path.join(BASE, "results/java/results_v9_testfix_math.csv")),
]


def checkout_bug(project, bug_id, target_dir):
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir)
    result = subprocess.run(
        ['defects4j', 'checkout', '-p', project, '-v', f'{bug_id}b', '-w', target_dir],
        capture_output=True, text=True, timeout=120
    )
    return os.path.exists(target_dir)


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


def apply_fix_to_file(full_file_path, original_line, fixed_line):
    with open(full_file_path) as f:
        lines = f.readlines()
    match_indices = [i for i, line in enumerate(lines) if line.strip() == original_line.strip()]
    if not match_indices:
        return False, match_indices
    i = match_indices[0]
    indent = len(lines[i]) - len(lines[i].lstrip())
    lines[i] = " " * indent + fixed_line.strip() + "\n"
    with open(full_file_path, "w") as f:
        f.writelines(lines)
    return True, match_indices


def find_source_file(tmp_dir, file_path, src_candidates):
    for src in src_candidates:
        candidate = os.path.join(tmp_dir, src, file_path) if src else os.path.join(tmp_dir, file_path)
        if os.path.exists(candidate):
            return candidate
    return None


SRC_CANDIDATES = ["source", "src", "src/main/java", ""]

for project, bug_id, results_csv in BUGS_TO_CHECK:
    print(f"\n=== {project}_{bug_id}: fix applied once, tested {N_RUNS}x ===")

    row = None
    with open(results_csv) as f:
        for r in csv.DictReader(f):
            if r['bug_id'] == bug_id:
                row = r
                break
    if row is None:
        print(f"  Could not find {bug_id} in {results_csv}")
        continue

    original_code = row.get('original_code', '')
    fixed_code = row.get('fixed_code', '')
    print(f"  ORIGINAL (from CSV): {original_code!r}")
    print(f"  FIXED    (from CSV): {fixed_code!r}")

    import json
    data_path = os.path.join(BASE, "data/bugs", f"{project}_{bug_id}", "data.json")
    with open(data_path) as f:
        data = json.load(f)
    file_path = data.get('file_path', '')

    tmp_dir = f"/tmp/{project}_{bug_id}_flaky_fixed"
    print("  Checking out fresh...")
    if not checkout_bug(project, bug_id, tmp_dir):
        print("  Checkout failed, skipping")
        continue

    full_path = find_source_file(tmp_dir, file_path, SRC_CANDIDATES)
    if not full_path:
        print(f"  Source file not found for {file_path}")
        continue

    # how many places in the file does the ORIGINAL string match?
    with open(full_path) as f:
        all_lines = f.readlines()
    match_indices_preview = [i for i, l in enumerate(all_lines) if l.strip() == original_code.strip()]
    print(f"  '{original_code.strip()}' appears at line(s): {[i+1 for i in match_indices_preview]} "
          f"(1-indexed) -- {'AMBIGUOUS, multiple matches!' if len(match_indices_preview) > 1 else 'unique match'}")

    applied, _ = apply_fix_to_file(full_path, original_code, fixed_code)
    if not applied:
        print("  Fix did not apply (no matching line found) -- this alone would explain a discrepancy")
        shutil.rmtree(tmp_dir, ignore_errors=True)
        continue

    all_runs = []
    for run_num in range(1, N_RUNS + 1):
        failing = capture_failing_tests(tmp_dir)
        all_runs.append(failing)
        print(f"  Run {run_num}: {len(failing)} failing -> {sorted(failing)}")

    baseline = all_runs[0]
    all_same = all(r == baseline for r in all_runs)
    print(f"  ALL {N_RUNS} POST-FIX RUNS IDENTICAL: {all_same}")

    shutil.rmtree(tmp_dir, ignore_errors=True)

print("\nDone.")

