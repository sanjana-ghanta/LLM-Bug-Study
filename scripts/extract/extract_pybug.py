import json
import os
import subprocess
import sys

BUGSINPY_DIR = os.path.expanduser("~/bugsinpy_workspace/BugsInPy/projects")

def get_changed_file(project, bug_id):
    """Read bug_patch.txt to find which file changed."""
    patch_path = f"{BUGSINPY_DIR}/{project}/bugs/{bug_id}/bug_patch.txt"
    with open(patch_path) as f:
        for line in f:
            if line.startswith("diff --git"):
                # e.g. "diff --git a/pandas/core/dtypes/common.py b/..."
                parts = line.strip().split(" ")
                file_path = parts[2][2:]  # strip "a/"
                return file_path
    return None

def get_commit_ids(project, bug_id):
    """Read bug.info to get buggy and fixed commit IDs."""
    info_path = f"{BUGSINPY_DIR}/{project}/bugs/{bug_id}/bug.info"
    buggy_commit = None
    fixed_commit = None
    with open(info_path) as f:
        for line in f:
            if line.startswith("buggy_commit_id"):
                buggy_commit = line.split("=")[1].strip().strip('"')
            elif line.startswith("fixed_commit_id"):
                fixed_commit = line.split("=")[1].strip().strip('"')
    return buggy_commit, fixed_commit

def get_file_at_commit(repo_dir, commit, file_path):
    """Use git show to get file contents at a specific commit."""
    result = subprocess.run(
        ["git", "show", f"{commit}:{file_path}"],
        capture_output=True, text=True, cwd=repo_dir
    )
    if result.returncode != 0:
        return None
    return result.stdout

def extract_pybug(project, bug_id, repo_dir):
    """Extract buggy and patched versions of the changed file."""
    file_path = get_changed_file(project, bug_id)
    if not file_path:
        print(f"Could not find changed file for {project}-{bug_id}")
        return False

    buggy_commit, fixed_commit = get_commit_ids(project, bug_id)
    if not buggy_commit or not fixed_commit:
        print(f"Could not find commit IDs for {project}-{bug_id}")
        return False

    print(f"  File: {file_path}")
    print(f"  Buggy commit: {buggy_commit}")
    print(f"  Fixed commit: {fixed_commit}")

    buggy_code = get_file_at_commit(repo_dir, buggy_commit, file_path)
    patched_code = get_file_at_commit(repo_dir, fixed_commit, file_path)

    if not buggy_code or not patched_code:
        print(f"  Could not retrieve file contents")
        return False

    out = {
        "project": project,
        "bug_id": bug_id,
        "file_path": file_path,
        "language": "python",
        "buggy_code": buggy_code,
        "patched_code": patched_code
    }

    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../data/pybugs", f"{project}_{bug_id}")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "data.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)

    print(f"  Saved to {out_path}")
    return True

if __name__ == "__main__":
    project = sys.argv[1]
    bug_id = sys.argv[2]
    repo_dir = sys.argv[3]
    extract_pybug(project, bug_id, repo_dir)
