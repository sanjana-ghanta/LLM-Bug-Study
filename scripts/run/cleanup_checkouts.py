"""
Deletes the buggy/ and patched/ checkout subdirectories for any bug that's
already been fully extracted into data.json (has a real original_bug_line,
not None). Everything downstream (SPM injection, tier5 generation,
detection) only ever reads from data.json -- the raw checkouts are pure
dead weight once original_bug_line is set.

Bugs still stuck at original_bug_line=None keep their checkouts, in case
you want to debug or retry the line-detection step differently later.

Read-only dry run by default -- pass --delete to actually remove anything.

Usage:
    python3 cleanup_checkouts.py            # dry run, shows what WOULD be deleted
    python3 cleanup_checkouts.py --delete   # actually deletes
"""

import json
import os
import shutil
import sys
import subprocess

BUGS_DIR = os.path.expanduser("~/llm-bug-study/experiment/data/bugs")


def get_dir_size(path):
    if not os.path.exists(path):
        return 0
    result = subprocess.run(["du", "-sk", path], capture_output=True, text=True)
    try:
        return int(result.stdout.split()[0]) * 1024  # du -k gives KB
    except (ValueError, IndexError):
        return 0


def human_size(num_bytes):
    for unit in ["B", "KB", "MB", "GB"]:
        if num_bytes < 1024:
            return f"{num_bytes:.1f}{unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f}TB"


def main():
    dry_run = "--delete" not in sys.argv

    total_would_free = 0
    resolved_count = 0
    unresolved_count = 0
    unresolved_bugs = []

    for bug_dir in sorted(os.listdir(BUGS_DIR)):
        data_path = os.path.join(BUGS_DIR, bug_dir, "data.json")
        if not os.path.exists(data_path):
            continue
        with open(data_path) as f:
            data = json.load(f)

        buggy_dir = os.path.join(BUGS_DIR, bug_dir, "buggy")
        patched_dir = os.path.join(BUGS_DIR, bug_dir, "patched")

        if data.get("original_bug_line") is not None:
            resolved_count += 1
            size = get_dir_size(buggy_dir) + get_dir_size(patched_dir)
            total_would_free += size
            if dry_run:
                if size > 0:
                    print(f"  [would delete] {bug_dir}: {human_size(size)}")
            else:
                if os.path.exists(buggy_dir):
                    shutil.rmtree(buggy_dir)
                if os.path.exists(patched_dir):
                    shutil.rmtree(patched_dir)
                if size > 0:
                    print(f"  [deleted] {bug_dir}: freed {human_size(size)}")
        else:
            unresolved_count += 1
            unresolved_bugs.append(bug_dir)

    print(f"\n{'='*60}")
    print(f"Resolved bugs (checkouts {'would be' if dry_run else 'were'} removed): {resolved_count}")
    print(f"Unresolved bugs (checkouts KEPT, original_bug_line=None): {unresolved_count}")
    if unresolved_bugs:
        print(f"  Kept: {unresolved_bugs}")
    print(f"\nTotal space {'that would be freed' if dry_run else 'freed'}: {human_size(total_would_free)}")

    if dry_run:
        print(f"\nThis was a DRY RUN -- nothing was deleted.")
        print(f"Run with --delete to actually remove these directories.")


if __name__ == "__main__":
    main()

