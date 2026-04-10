import json
import os
import time
import csv
import anthropic

client = anthropic.Anthropic()

def truncate_code(code, max_lines=80):
    lines = code.splitlines()
    if len(lines) > max_lines:
        return "\n".join(lines[:max_lines]) + "\n... (truncated)"
    return code

def ask_claude_with_lineno(code, file_path):
    code = truncate_code(code, max_lines=80)
    prompt = f"""Review the following code from {file_path} and determine if it contains a bug.
Respond in this exact format:
VERDICT: BUG or NO BUG
LINE: <line number where the bug is, or NONE if no bug>
REASON: <one sentence explanation>

Code:
{code}"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}]
    )
    
    text = response.content[0].text.strip()
    verdict = "BUG" if "VERDICT: BUG" in text else "NO BUG"
    
    # Extract line number
    line_no = None
    for line in text.splitlines():
        if line.startswith("LINE:"):
            val = line.replace("LINE:", "").strip()
            if val.isdigit():
                line_no = int(val)
    
    return verdict, line_no, text

def classify_bug_found(reported_line, original_bug_line, spm_line, tolerance=5):
    """Classify which bug Claude found based on reported line number."""
    if reported_line is None:
        return "none"
    if original_bug_line and abs(reported_line - original_bug_line) <= tolerance:
        return "original"
    if spm_line and abs(reported_line - spm_line) <= tolerance:
        return "spm"
    return "other"

def load_completed(csv_path):
    completed = set()
    if os.path.exists(csv_path):
        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                completed.add((row["project"], row["bug_id"], row["tier"]))
    return completed

def process_bug(data_json_path, writer, completed, language="java"):
    with open(data_json_path) as f:
        data = json.load(f)

    project = data["project"]
    bug_id = str(data["bug_id"])
    file_path = data["file_path"]
    original_bug_line = data.get("original_bug_line")

    tiers = {
        1: ("patched_code", "NO BUG", None),
        2: ("buggy_code", "BUG", None),
        3: ("tier3_code", "BUG", data.get("tier3_mutation_line")),
        4: ("tier4_code", "BUG", data.get("tier4_mutation_line")),
        5: ("tier5_code", "BUG", None),
    }

    for tier_num, (code_key, expected, spm_line) in tiers.items():
        if (project, bug_id, str(tier_num)) in completed:
            print(f"  Skipping tier {tier_num} for {project}-{bug_id}")
            continue

        code = data.get(code_key)
        if not code:
            continue

        print(f"  Running tier {tier_num} for {project}-{bug_id}...")
        try:
            verdict, reported_line, full_response = ask_claude_with_lineno(code, file_path)
        except anthropic.RateLimitError:
            print("  Rate limit, waiting 90s...")
            time.sleep(90)
            verdict, reported_line, full_response = ask_claude_with_lineno(code, file_path)

        correct = verdict == expected
        bug_found = classify_bug_found(reported_line, original_bug_line, spm_line)

        writer.writerow({
            "project": project,
            "bug_id": bug_id,
            "language": language,
            "tier": tier_num,
            "expected": expected,
            "verdict": verdict,
            "correct": correct,
            "reported_line": reported_line,
            "original_bug_line": original_bug_line,
            "spm_line": spm_line,
            "bug_found": bug_found,
            "response": full_response.replace("\n", " ")
        })
        time.sleep(8)

if __name__ == "__main__":
    OUT_CSV = "/Users/sunny/llm-bug-study/experiment/results_lineno.csv"
    fields = [
        "project", "bug_id", "language", "tier", "expected",
        "verdict", "correct", "reported_line", "original_bug_line",
        "spm_line", "bug_found", "response"
    ]

    completed = load_completed(OUT_CSV)
    print(f"Already completed: {len(completed)} results")

    with open(OUT_CSV, "a", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fields)
        if len(completed) == 0:
            writer.writeheader()

        # Java bugs
        JAVA_DIR = "/Users/sunny/llm-bug-study/experiment/bugs"
        for bug_dir in sorted(os.listdir(JAVA_DIR)):
            data_path = os.path.join(JAVA_DIR, bug_dir, "data.json")
            if os.path.exists(data_path):
                print(f"Processing Java {bug_dir}...")
                process_bug(data_path, writer, completed, language="java")
                csvfile.flush()

        # Python bugs
        PY_DIR = "/Users/sunny/llm-bug-study/experiment/pybugs"
        for bug_dir in sorted(os.listdir(PY_DIR)):
            data_path = os.path.join(PY_DIR, bug_dir, "data.json")
            if os.path.exists(data_path):
                print(f"Processing Python {bug_dir}...")
                process_bug(data_path, writer, completed, language="python")
                csvfile.flush()

    print(f"Done! Results saved to {OUT_CSV}")
