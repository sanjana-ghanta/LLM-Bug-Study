import json
import os
import subprocess
import sys

def get_modified_file(project, bug_id):
    result = subprocess.run(
        ["defects4j", "info", "-p", project, "-b", str(bug_id)],
        capture_output=True, text=True
    )
    in_modified = False
    for line in result.stdout.splitlines():
        if "List of modified sources" in line:
            in_modified = True
            continue
        if in_modified and line.strip().startswith("-"):
            class_name = line.strip().lstrip("- ").strip()
            file_path = class_name.replace(".", "/") + ".java"
            return file_path
    return None

def read_file(base_dir, file_path):
    # Try all known src layouts
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
    raise FileNotFoundError(f"Could not find {file_path} under {base_dir}")

def extract_bug(project, bug_id):
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../data/bugs", f"{project}_{bug_id}")
    buggy_dir = os.path.join(base, "buggy")
    patched_dir = os.path.join(base, "patched")

    file_path = get_modified_file(project, bug_id)
    if not file_path:
        print(f"Could not find modified file for {project}-{bug_id}")
        return

    print(f"Modified file: {file_path}")

    buggy_code = read_file(buggy_dir, file_path)
    patched_code = read_file(patched_dir, file_path)

    out = {
        "project": project,
        "bug_id": bug_id,
        "file_path": file_path,
        "buggy_code": buggy_code,
        "patched_code": patched_code
    }

    out_path = os.path.join(base, "data.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)

    print(f"Saved to {out_path}")

if __name__ == "__main__":
    project = sys.argv[1]
    bug_id = sys.argv[2]
    extract_bug(project, bug_id)
