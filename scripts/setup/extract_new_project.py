"""
Checks out and extracts every active bug for a Defects4J project that isn't
in the dataset yet (e.g. Time, Mockito). After this runs, the EXISTING
extract_bug_line.py and inject_spm.py scripts will pick up the new bugs
automatically -- they already loop over whatever's in data/bugs/ and skip
anything already done, so they need no changes for a new project.

Usage:
    python3 extract_new_project.py Time
    python3 extract_new_project.py Mockito
"""

import json
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BUGS_DIR = os.path.join(BASE, "data/bugs")


def get_active_bug_ids(project):
    """Uses `defects4j bids` to get the real list of active (non-deprecated)
    bug IDs for a project, instead of assuming/guessing a range."""
    result = subprocess.run(
        ["defects4j", "bids", "-p", project],
        capture_output=True, text=True, timeout=60
    )
    ids = [int(line.strip()) for line in result.stdout.splitlines() if line.strip().isdigit()]
    return sorted(ids)


def get_modified_file(project, bug_id):
    result = subprocess.run(
        ["defects4j", "info", "-p", project, "-b", str(bug_id)],
        capture_output=True, text=True, timeout=60
    )
    in_modified = False
    for line in result.stdout.splitlines():
        if "List of modified sources" in line:
            in_modified = True
            continue
        if in_modified and line.strip().startswith("-"):
            class_name = line.strip().lstrip("- ").strip()
            return class_name.replace(".", "/") + ".java"
    return None


def read_file(base_dir, file_path):
    candidates = [
        os.path.join(base_dir, "src/main/java", file_path),
        os.path.join(base_dir, "src/java", file_path),
        os.path.join(base_dir, "source", file_path),
        os.path.join(base_dir, "src", file_path),
    ]
    for full_path in candidates:
        if os.path.exists(full_path):
            with open(full_path, "r") as f:
                return f.read()
    return None


def checkout_and_extract(project, bug_id):
    out_dir = os.path.join(BUGS_DIR, f"{project}_{bug_id}")
    data_path = os.path.join(out_dir, "data.json")

    if os.path.exists(data_path):
        print(f"  Skipping {project}-{bug_id}, already extracted")
        return

    buggy_dir = os.path.join(out_dir, "buggy")
    patched_dir = os.path.join(out_dir, "patched")

    print(f"  Checking out {project}-{bug_id}...")
    subprocess.run(["defects4j", "checkout", "-p", project, "-v", f"{bug_id}b", "-w", buggy_dir],
                    capture_output=True, timeout=120)
    subprocess.run(["defects4j", "checkout", "-p", project, "-v", f"{bug_id}f", "-w", patched_dir],
                    capture_output=True, timeout=120)

    if not os.path.exists(buggy_dir) or not os.path.exists(patched_dir):
        print(f"  FAILED checkout for {project}-{bug_id}, skipping")
        return

    file_path = get_modified_file(project, bug_id)
    if not file_path:
        print(f"  Could not determine modified file for {project}-{bug_id}, skipping")
        return

    buggy_code = read_file(buggy_dir, file_path)
    patched_code = read_file(patched_dir, file_path)
    if buggy_code is None or patched_code is None:
        print(f"  Could not read {file_path} for {project}-{bug_id} under known src layouts, skipping")
        return

    os.makedirs(out_dir, exist_ok=True)
    with open(data_path, "w") as f:
        json.dump({
            "project": project,
            "bug_id": bug_id,
            "file_path": file_path,
            "buggy_code": buggy_code,
            "patched_code": patched_code,
        }, f, indent=2)
    print(f"  Extracted {project}-{bug_id} ({file_path})")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 extract_new_project.py <ProjectName>")
        sys.exit(1)

    project = sys.argv[1]
    bug_ids = get_active_bug_ids(project)
    print(f"{project}: {len(bug_ids)} active bugs found via `defects4j bids`")

    for bug_id in bug_ids:
        checkout_and_extract(project, bug_id)

    print(f"\nDone extracting {project}.")
    print("Next steps (these already generalize to any project automatically):")
    print("  python3 ../extract/extract_bug_line.py")
    print("  python3 ../inject/inject_spm.py")
    print("  python3 ../inject/generate_tier5_multimodel.py --model <each model>")


if __name__ == "__main__":
    main()

