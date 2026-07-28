"""
Test-flip experiment (follow-up to Experiment 9).

Reuses the fixes already computed in results_v9_testfix*.csv (no new Claude
calls needed) and re-runs the test suite before/after each fix, capturing
the SET of failing test names (not just the count). This lets us determine,
per bug, exactly which tests flip from failing to passing (or the reverse),
rather than inferring it from a count that can hide cancelling changes.

Per Prof. Gulzar's framing: the test suite is the only ground truth we have.
A bug's line is "verified buggy" to the extent that fixing it flips a real
failing test to passing.
"""

import os
import csv
import json
import re
import shutil
import subprocess
import time

BASE = os.path.expanduser("~/llm-bug-study/experiment")
BUGS_DIR = os.path.join(BASE, "data/bugs")
OUT_CSV = os.path.join(BASE, "results/java/results_testflip.csv")

PROJECTS = [
    {
        "name": "Chart",
        "results_csv": os.path.join(BASE, "results/java/results_v9_testfix.csv"),
        "src_candidates": ["source", "src", "src/main/java", ""],
    },
    {
        "name": "Lang",
        "results_csv": os.path.join(BASE, "results/java/results_v9_testfix_lang.csv"),
        "src_candidates": ["src/main/java", "src", "source", ""],
    },
    {
        "name": "Math",
        "results_csv": os.path.join(BASE, "results/java/results_v9_testfix_math.csv"),
        "src_candidates": ["src/main/java", "src", "source", ""],
    },
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
    """Run defects4j test and return (passed, n_failing, set_of_test_names)."""
    result = subprocess.run(
        ['defects4j', 'test', '-w', checkout_dir],
        capture_output=True, text=True, timeout=300
    )
    output = result.stdout + result.stderr

    # defects4j writes a `failing_tests` file into the workdir on each run;
    # each failing entry starts with "--- ClassName::methodName"
    names = set()
    failing_tests_path = os.path.join(checkout_dir, 'failing_tests')
    if os.path.exists(failing_tests_path):
        with open(failing_tests_path) as f:
            content = f.read()
        names = set(re.findall(r'--- (\S+)', content))

    if not names:
        # fallback: parse stdout lines like "  - full.Class::method"
        names = set(re.findall(r'^\s*-\s+(\S+)', output, re.MULTILINE))

    n_failing = len(names)
    if n_failing == 0:
        fail_match = re.search(r'Failing tests: (\d+)', output)
        if fail_match:
            n_failing = int(fail_match.group(1))

    passed = n_failing == 0
    return passed, n_failing, names


def apply_fix_to_file(full_file_path, original_line, fixed_line):
    with open(full_file_path) as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        if line.strip() == original_line.strip():
            indent = len(line) - len(line.lstrip())
            lines[i] = " " * indent + fixed_line.strip() + "\n"
            with open(full_file_path, "w") as f:
                f.writelines(lines)
            return True
    return False


def find_source_file(tmp_dir, file_path, src_candidates):
    for src in src_candidates:
        candidate = os.path.join(tmp_dir, src, file_path) if src else os.path.join(tmp_dir, file_path)
        if os.path.exists(candidate):
            return candidate
    return None


fields = [
    'project', 'bug_id', 'file', 'actual_line', 'claude_line',
    'n_before', 'n_after',
    'flipped_to_pass', 'flipped_to_fail', 'still_failing',
    'n_flipped_to_pass', 'n_flipped_to_fail',
    'any_flip_to_pass', 'clean_pass',
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

    for proj in PROJECTS:
        project = proj["name"]
        if not os.path.exists(proj["results_csv"]):
            print(f"Skipping {project}: {proj['results_csv']} not found")
            continue

        with open(proj["results_csv"]) as f:
            rows = list(csv.DictReader(f))

        print(f"\n=== {project}: {len(rows)} bugs from prior Experiment 9 run ===")

        for row in rows:
            bug_id = row['bug_id']
            if (project, bug_id) in completed:
                print(f"  Skipping {project}_{bug_id} (already done)")
                continue

            # only bugs where Experiment 9 actually applied a fix are worth re-testing
            if row.get('fix_applied', 'False') != 'True':
                print(f"  Skipping {project}_{bug_id} (no fix was applied in Exp 9)")
                continue

            original_code = row.get('original_code', '')
            fixed_code = row.get('fixed_code', '')
            if not original_code or not fixed_code:
                continue

            actual_line = row.get('actual_line', '')
            claude_line = row.get('claude_line', '')
            filename = row.get('file', '')

            data_path = os.path.join(BUGS_DIR, f"{project}_{bug_id}", "data.json")
            if not os.path.exists(data_path):
                print(f"  No data.json for {project}_{bug_id}, skipping")
                continue
            with open(data_path) as f:
                data = json.load(f)
            file_path = data.get('file_path', '')

            print(f"\n{project}_{bug_id} | actual={actual_line} claude={claude_line}")

            tmp_dir = f"/tmp/{project}_{bug_id}_flip"
            print("  Checking out...")
            if not checkout_bug(project, bug_id, tmp_dir):
                print("  Checkout failed")
                continue

            print("  Capturing failing tests BEFORE fix...")
            _, n_before, before_tests = capture_failing_tests(tmp_dir)
            print(f"  Failing before: {n_before}")

            full_path = find_source_file(tmp_dir, file_path, proj["src_candidates"])
            if not full_path:
                print(f"  Source file not found for {file_path}")
                shutil.rmtree(tmp_dir, ignore_errors=True)
                continue

            fix_applied = apply_fix_to_file(full_path, original_code, fixed_code)
            if not fix_applied:
                print("  Could not locate original line to apply fix")
                shutil.rmtree(tmp_dir, ignore_errors=True)
                continue

            print("  Capturing failing tests AFTER fix...")
            _, n_after, after_tests = capture_failing_tests(tmp_dir)
            print(f"  Failing after: {n_after}")

            flipped_to_pass = before_tests - after_tests
            flipped_to_fail = after_tests - before_tests
            still_failing = before_tests & after_tests

            print(f"  Flipped to pass: {len(flipped_to_pass)} | "
                  f"Flipped to fail (regressions): {len(flipped_to_fail)} | "
                  f"Still failing: {len(still_failing)}")

            writer.writerow({
                'project': project,
                'bug_id': bug_id,
                'file': filename,
                'actual_line': actual_line,
                'claude_line': claude_line,
                'n_before': n_before,
                'n_after': n_after,
                'flipped_to_pass': ";".join(sorted(flipped_to_pass)),
                'flipped_to_fail': ";".join(sorted(flipped_to_fail)),
                'still_failing': ";".join(sorted(still_failing)),
                'n_flipped_to_pass': len(flipped_to_pass),
                'n_flipped_to_fail': len(flipped_to_fail),
                'any_flip_to_pass': len(flipped_to_pass) > 0,
                'clean_pass': n_after == 0,
            })
            csvfile.flush()
            shutil.rmtree(tmp_dir, ignore_errors=True)
            time.sleep(2)

print(f"\nDone! Results saved to {OUT_CSV}")

