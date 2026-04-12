import subprocess
import os
import sys

REPO_DIR = os.path.expanduser("~/llm-bug-study/experiment/pyrepos")

bugs = (
    [("pandas", i) for i in range(1, 26)] +
    [("black", i) for i in range(1, 16)] +
    [("thefuck", i) for i in range(1, 11)]
)

for project, bug_id in bugs:
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../data/pybugs", f"{project}_{bug_id}")
    data_path = os.path.join(out_dir, "data.json")

    if os.path.exists(data_path):
        print(f"Skipping {project}-{bug_id}, already done")
        continue

    print(f"Extracting {project}-{bug_id}...")
    repo_dir = os.path.join(REPO_DIR, project)
    result = subprocess.run(
        ["python3", "/Users/sunny/llm-bug-study/experiment/extract_pybug.py", 
         project, str(bug_id), repo_dir],
        capture_output=False
    )

print("All done!")
