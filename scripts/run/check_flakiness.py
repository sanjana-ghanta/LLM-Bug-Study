"""
Flakiness check for Chart_26 and Math_16 — no fix applied, just repeated
`defects4j test` runs on a fresh checkout of the buggy version, to see
whether the failing-test set itself is unstable across runs.
"""

import os
import re
import shutil
import subprocess

N_RUNS = 5  # number of repeated test runs per bug

BUGS_TO_CHECK = [
    ("Chart", "26"),
    ("Math", "16"),
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


for project, bug_id in BUGS_TO_CHECK:
    print(f"\n=== {project}_{bug_id}: {N_RUNS} repeated runs, no fix applied ===")
    tmp_dir = f"/tmp/{project}_{bug_id}_flaky"

    print("  Checking out (once, reused across all runs)...")
    if not checkout_bug(project, bug_id, tmp_dir):
        print("  Checkout failed, skipping")
        continue

    all_runs = []
    for run_num in range(1, N_RUNS + 1):
        failing = capture_failing_tests(tmp_dir)
        all_runs.append(failing)
        print(f"  Run {run_num}: {len(failing)} failing -> {sorted(failing)}")

    baseline = all_runs[0]
    all_same = all(r == baseline for r in all_runs)
    print(f"  ALL {N_RUNS} RUNS IDENTICAL: {all_same}")
    if not all_same:
        for i, r in enumerate(all_runs[1:], start=2):
            diff_added = r - baseline
            diff_removed = baseline - r
            if diff_added or diff_removed:
                print(f"    Run {i} vs Run 1: +{sorted(diff_added)} -{sorted(diff_removed)}")

    shutil.rmtree(tmp_dir, ignore_errors=True)

print("\nDone.")

