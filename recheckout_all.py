import subprocess
import os

BUGS_DIR = "/Users/sunny/llm-bug-study/experiment/bugs"

bugs = (
    [("Lang", i) for i in range(1, 21)] +
    [("Math", i) for i in range(1, 21)] +
    [("Chart", i) for i in range(1, 11)]
)

def is_checked_out(buggy_dir):
    for src in ["src", "source"]:
        if os.path.exists(os.path.join(buggy_dir, src)):
            return True
    return False

for project, bug_id in bugs:
    outdir = f"{BUGS_DIR}/{project}_{bug_id}"
    buggy_dir = f"{outdir}/buggy"
    patched_dir = f"{outdir}/patched"

    if os.path.exists(f"{outdir}/data.json"):
        print(f"Skipping {project}-{bug_id}, already done")
        continue

    if not is_checked_out(buggy_dir):
        print(f"Checking out {project}-{bug_id}...")
        subprocess.run(["defects4j", "checkout", "-p", project, "-v", f"{bug_id}b", "-w", buggy_dir], capture_output=True)
        subprocess.run(["defects4j", "checkout", "-p", project, "-v", f"{bug_id}f", "-w", patched_dir], capture_output=True)

    if is_checked_out(buggy_dir):
        print(f"Extracting {project}-{bug_id}...")
        subprocess.run(["python3", "/Users/sunny/llm-bug-study/experiment/extract_bug.py", project, str(bug_id)])
    else:
        print(f"FAILED checkout for {project}-{bug_id}, skipping")

print("All done!")
