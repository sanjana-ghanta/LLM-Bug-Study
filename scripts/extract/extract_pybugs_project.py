"""
Generalized BugsInPy extraction: works for any of BugsInPy's 17 projects,
not just the original 3. Automatically clones the project's own source
repo (from BugsInPy's project.info) if it isn't already present, then
extracts every bug BugsInPy tracks for that project via git show against
the buggy/fixed commit IDs.

Usage:
    python3 extract_pybugs_project.py pandas
    python3 extract_pybugs_project.py black
"""

import json
import os
import subprocess
import sys

BUGSINPY_DIR = os.path.expanduser("~/bugsinpy_workspace/BugsInPy/projects")
REPO_DIR = os.path.expanduser("~/llm-bug-study/experiment/pyrepos")
DATA_DIR = os.path.expanduser("~/llm-bug-study/experiment/data/pybugs")


def get_project_github_url(project):
    info_path = os.path.join(BUGSINPY_DIR, project, "project.info")
    with open(info_path) as f:
        for line in f:
            if line.startswith("github_url"):
                return line.split("=", 1)[1].strip().strip('"')
    return None


def ensure_repo_cloned(project):
    repo_dir = os.path.join(REPO_DIR, project)
    if os.path.exists(os.path.join(repo_dir, ".git")):
        print(f"  {project} repo already cloned at {repo_dir}")
        return repo_dir

    github_url = get_project_github_url(project)
    if not github_url:
        print(f"  Could not find github_url for {project} in project.info")
        return None

    print(f"  Cloning {github_url} into {repo_dir}...")
    os.makedirs(REPO_DIR, exist_ok=True)
    result = subprocess.run(
        ["git", "clone", github_url, repo_dir],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  FAILED to clone {project}: {result.stderr[:300]}")
        return None
    return repo_dir


def get_bug_ids(project):
    bugs_dir = os.path.join(BUGSINPY_DIR, project, "bugs")
    if not os.path.exists(bugs_dir):
        return []
    ids = [d for d in os.listdir(bugs_dir) if d.isdigit()]
    return sorted(ids, key=int)


def get_changed_file(project, bug_id):
    patch_path = os.path.join(BUGSINPY_DIR, project, "bugs", bug_id, "bug_patch.txt")
    with open(patch_path) as f:
        for line in f:
            if line.startswith("diff --git"):
                parts = line.strip().split(" ")
                return parts[2][2:]  # strip "a/" prefix
    return None


def get_commit_ids(project, bug_id):
    info_path = os.path.join(BUGSINPY_DIR, project, "bugs", bug_id, "bug.info")
    buggy_commit = fixed_commit = None
    with open(info_path) as f:
        for line in f:
            if line.startswith("buggy_commit_id"):
                buggy_commit = line.split("=", 1)[1].strip().strip('"')
            elif line.startswith("fixed_commit_id"):
                fixed_commit = line.split("=", 1)[1].strip().strip('"')
    return buggy_commit, fixed_commit


def get_file_at_commit(repo_dir, commit, file_path):
    result = subprocess.run(
        ["git", "show", f"{commit}:{file_path}"],
        capture_output=True, text=True, cwd=repo_dir
    )
    if result.returncode != 0:
        return None
    return result.stdout


def extract_one_bug(project, bug_id, repo_dir):
    out_dir = os.path.join(DATA_DIR, f"{project}_{bug_id}")
    data_path = os.path.join(out_dir, "data.json")
    if os.path.exists(data_path):
        print(f"  Skipping {project}-{bug_id}, already done")
        return

    file_path = get_changed_file(project, bug_id)
    if not file_path:
        print(f"  {project}-{bug_id}: could not find changed file, skipping")
        return

    buggy_commit, fixed_commit = get_commit_ids(project, bug_id)
    if not buggy_commit or not fixed_commit:
        print(f"  {project}-{bug_id}: could not find commit IDs, skipping")
        return

    buggy_code = get_file_at_commit(repo_dir, buggy_commit, file_path)
    patched_code = get_file_at_commit(repo_dir, fixed_commit, file_path)
    if not buggy_code or not patched_code:
        print(f"  {project}-{bug_id}: could not retrieve file contents, skipping")
        return

    os.makedirs(out_dir, exist_ok=True)
    with open(data_path, "w") as f:
        json.dump({
            "project": project,
            "bug_id": bug_id,
            "file_path": file_path,
            "language": "python",
            "buggy_code": buggy_code,
            "patched_code": patched_code,
        }, f, indent=2)
    print(f"  Extracted {project}-{bug_id} ({file_path})")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 extract_pybugs_project.py <project_name>")
        sys.exit(1)

    project = sys.argv[1]
    repo_dir = ensure_repo_cloned(project)
    if not repo_dir:
        print(f"Could not set up repo for {project}, aborting.")
        sys.exit(1)

    bug_ids = get_bug_ids(project)
    print(f"{project}: {len(bug_ids)} bugs tracked by BugsInPy")

    for bug_id in bug_ids:
        extract_one_bug(project, bug_id, repo_dir)

    print(f"Done extracting {project}.")


if __name__ == "__main__":
    main()

