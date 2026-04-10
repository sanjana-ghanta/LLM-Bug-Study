import json
import os
import subprocess

def get_bug_line_java(project, bug_id):
    """Get the line number of the original bug from the diff."""
    base = f"/Users/sunny/llm-bug-study/experiment/bugs/{project}_{bug_id}"
    buggy_dir = os.path.join(base, "buggy")
    patched_dir = os.path.join(base, "patched")

    # Find the source file
    data_path = os.path.join(base, "data.json")
    with open(data_path) as f:
        data = json.load(f)
    file_path = data["file_path"]

    # Try different src layouts
    for src in ["src/main/java", "src/java", "source"]:
        buggy_file = os.path.join(buggy_dir, src, file_path)
        patched_file = os.path.join(patched_dir, src, file_path)
        if os.path.exists(buggy_file) and os.path.exists(patched_file):
            result = subprocess.run(
                ["diff", buggy_file, patched_file],
                capture_output=True, text=True
            )
            # Parse diff output to find first changed line
            for line in result.stdout.splitlines():
                if line[0].isdigit():
                    # e.g. "466a467,475" or "468c477"
                    num = line.split("a")[0].split("c")[0].split("d")[0]
                    try:
                        return int(num)
                    except:
                        continue
    return None

def get_bug_line_python(project, bug_id):
    """Get the line number from bug_patch.txt for Python bugs."""
    patch_path = f"/Users/sunny/bugsinpy_workspace/BugsInPy/projects/{project}/bugs/{bug_id}/bug_patch.txt"
    with open(patch_path) as f:
        for line in f:
            if line.startswith("@@"):
                # e.g. "@@ -599,7 +599,7 @@"
                part = line.split("-")[1].split(",")[0]
                try:
                    return int(part)
                except:
                    continue
    return None

def process_all():
    # Java bugs
    JAVA_DIR = "/Users/sunny/llm-bug-study/experiment/bugs"
    for bug_dir in sorted(os.listdir(JAVA_DIR)):
        data_path = os.path.join(JAVA_DIR, bug_dir, "data.json")
        if not os.path.exists(data_path):
            continue
        with open(data_path) as f:
            data = json.load(f)
        if data.get("original_bug_line"):
            print(f"Skipping {bug_dir}, already done")
            continue
        project = data["project"]
        bug_id = data["bug_id"]
        line = get_bug_line_java(project, bug_id)
        data["original_bug_line"] = line
        with open(data_path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"{bug_dir}: original bug line = {line}")

    # Python bugs
    PY_DIR = "/Users/sunny/llm-bug-study/experiment/pybugs"
    for bug_dir in sorted(os.listdir(PY_DIR)):
        data_path = os.path.join(PY_DIR, bug_dir, "data.json")
        if not os.path.exists(data_path):
            continue
        with open(data_path) as f:
            data = json.load(f)
        if data.get("original_bug_line"):
            print(f"Skipping {bug_dir}, already done")
            continue
        project = data["project"]
        bug_id = data["bug_id"]
        line = get_bug_line_python(project, bug_id)
        data["original_bug_line"] = line
        with open(data_path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"{bug_dir}: original bug line = {line}")

    print("All done!")

if __name__ == "__main__":
    process_all()
