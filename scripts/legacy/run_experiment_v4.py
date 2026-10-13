import re
import json
import os
import csv
import time
import anthropic

client = anthropic.Anthropic()

BENCHMARK_NAME = {
    "Lang":  "Defects4J",
    "Math":  "Defects4J",
    "Chart": "Defects4J",
}

HINT_MAP = {
    "off_by_one":    "a boundary or range handling error",
    "operator_swap": "an arithmetic expression error",
    "boolean_logic": "a conditional logic error",
    None:            "a logic error",
}

def get_file_manifest(project_dir):
    manifest = []
    for root, dirs, files in os.walk(project_dir):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('build', 'target', '.svn', '.git')]
        for f in files:
            if f.endswith('.java'):
                rel_path = os.path.relpath(os.path.join(root, f), project_dir)
                manifest.append(rel_path)
    return sorted(manifest)

def get_package_files(project_dir, file_path):
    """Get all Java files in the same package as the changed file."""
    package_dir = os.path.dirname(file_path)
    results = []
    for root, dirs, files in os.walk(project_dir):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('build', 'target', '.svn', '.git')]
        rel_root = os.path.relpath(root, project_dir)
        if rel_root == package_dir or rel_root.replace('\\', '/') == package_dir:
            for f in files:
                if f.endswith('.java'):
                    full_path = os.path.join(root, f)
                    # skip the main file itself
                    if os.path.basename(file_path) not in f:
                        try:
                            with open(full_path, encoding='utf-8', errors='replace') as fh:
                                content = fh.read()
                            results.append(f"// FILE: {os.path.join(rel_root, f)}\n{content}")
                        except Exception:
                            pass
    return "\n\n".join(results) if results else "No additional package files found."

def find_test_file(project_dir, test_class):
    filename = test_class.split('.')[-1] + '.java'
    for root, dirs, files in os.walk(project_dir):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('build', 'target', '.svn', '.git')]
        if filename in files:
            return os.path.join(root, filename)
    return None

def read_file_content(path):
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            return f.read()
    except Exception:
        return None

def ask_llm(source_code, test_code, file_path, test_class, manifest, package_files, project, benchmark, hint):
    manifest_str = "\n".join(manifest[:200])
    if len(manifest) > 200:
        manifest_str += f"\n... and {len(manifest) - 200} more files"

    prompt = f"""You are analyzing code from the {benchmark} benchmark.

A bug is defined as a defect in the code that causes one or more test cases to fail.

This code contains a known issue related to {hint}.

Given the project structure, the source file under investigation, its related package files, and the test cases below, can you identify if there is a bug?

Please respond in this exact format:
VERDICT: BUG or NO BUG
LINE: <file path and line number where the bug is, or NONE if no bug>
REASON: <one sentence explanation of what specifically is wrong>

---

PROJECT STRUCTURE ({project}):
{manifest_str}

---

SOURCE FILE UNDER INVESTIGATION: {file_path}
{source_code}

---

RELATED PACKAGE FILES:
{package_files}

---

TEST FILE: {test_class}
{test_code if test_code else "Test file not found."}
"""

    for attempt in range(3):
        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}]
            )
            text = response.content[0].text.strip()
            verdict = "BUG" if "VERDICT: BUG" in text else "NO BUG"

            line_no = None
            for line in text.splitlines():
                if line.startswith("LINE:"):
                    val = line.replace("LINE:", "").strip()
                    match = re.match(r'\d+', val.strip()); digits = match.group(0) if match else ''
                    if digits:
                        line_no = int(digits)

            return verdict, line_no, text

        except Exception as e:
            if "rate" in str(e).lower():
                wait = 120 * (attempt + 1)
                print(f"  Rate limit, waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"  Error: {e}")
                return None, None, str(e)

    return None, None, "max retries exceeded"

def classify_bug_found(reported_line, original_bug_line, tolerance=5):
    if reported_line is None:
        return "none"
    if original_bug_line and abs(reported_line - original_bug_line) <= tolerance:
        return "original"
    return "other"

def load_completed(csv_path):
    completed = set()
    if os.path.exists(csv_path):
        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                completed.add((row["project"], row["bug_id"], row["tier"]))
    return completed

def process_bug(data_json_path, writer, completed):
    with open(data_json_path) as f:
        data = json.load(f)

    project           = data["project"]
    bug_id            = str(data["bug_id"])
    file_path         = data["file_path"]
    original_bug_line = data.get("original_bug_line")
    benchmark         = BENCHMARK_NAME.get(project, "Defects4J")
    test_class        = data.get("test_class", "")
    hint              = HINT_MAP.get(data.get("tier3_mutation_type"), HINT_MAP[None])

    tiers = {
        1: ("patched_code", "NO BUG", "patched"),
        2: ("buggy_code",   "BUG",    "buggy"),
    }

    for tier_num, (code_key, expected, checkout_dir) in tiers.items():
        if (project, bug_id, str(tier_num)) in completed:
            print(f"  Skipping tier {tier_num} for {project}-{bug_id}")
            continue

        source_code = data.get(code_key)
        if not source_code:
            print(f"  Skipping tier {tier_num} for {project}-{bug_id} (no code)")
            continue

        bug_dir     = os.path.dirname(data_json_path)
        project_dir = os.path.join(bug_dir, checkout_dir)

        if not os.path.exists(project_dir):
            print(f"  No checkout dir at {project_dir}, skipping")
            continue

        manifest      = get_file_manifest(project_dir)
        package_files = get_package_files(project_dir, file_path)

        test_code = None
        if test_class:
            test_path = find_test_file(project_dir, test_class)
            test_code = read_file_content(test_path)

        print(f"  Running tier {tier_num} for {project}-{bug_id} | hint: {hint} | {len(manifest)} files in manifest")

        verdict, reported_line, full_response = ask_llm(
            source_code, test_code, file_path, test_class,
            manifest, package_files, project, benchmark, hint
        )

        if verdict is None:
            print(f"  Failed, skipping")
            continue

        correct   = verdict == expected
        bug_found = classify_bug_found(reported_line, original_bug_line)

        writer.writerow({
            "project":           project,
            "bug_id":            bug_id,
            "tier":              tier_num,
            "hint":              hint,
            "mutation_type":     data.get("tier3_mutation_type"),
            "expected":          expected,
            "verdict":           verdict,
            "correct":           correct,
            "reported_line":     reported_line,
            "original_bug_line": original_bug_line,
            "bug_found":         bug_found,
            "manifest_size":     len(manifest),
            "has_test":          test_code is not None,
            "response":          full_response.replace("\n", " ")
        })
        time.sleep(10)

if __name__ == "__main__":
    BUGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../data/bugs")
    OUT_CSV  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../results/java/results_v4b_chart.csv")

    fields = [
        "project", "bug_id", "tier", "hint", "mutation_type",
        "expected", "verdict", "correct",
        "reported_line", "original_bug_line", "bug_found",
        "manifest_size", "has_test", "response"
    ]

    completed = load_completed(OUT_CSV)
    print(f"Already completed: {len(completed)} results")

    all_chart = sorted(
        [d for d in os.listdir(BUGS_DIR) if d.startswith("Chart")],
        key=lambda x: int(x.split("_")[1]),
        reverse=True
    )
    print(f"Running on {len(all_chart)} Chart bugs in reverse order")

    with open(OUT_CSV, "a", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fields)
        if len(completed) == 0:
            writer.writeheader()

        for bug_dir in all_chart:
            data_path = os.path.join(BUGS_DIR, bug_dir, "data.json")
            if os.path.exists(data_path):
                print(f"\nProcessing {bug_dir}...")
                process_bug(data_path, writer, completed)
                csvfile.flush()

    print(f"\nDone! Results saved to {OUT_CSV}")
