import json
import os
import time
import csv
import anthropic

client = anthropic.Anthropic()

JAVA_BUGS = ["Lang_1", "Lang_3", "Math_1", "Math_2", "Chart_1"]
PY_BUGS = ["pandas_1", "pandas_2", "black_1", "black_2", "thefuck_2"]

def ask_claude(code, file_path, benchmark):
    prompt = f"""This code is from a known bug in the {benchmark} benchmark. Can you help me identify the bug?

Please respond in this exact format:
VERDICT: BUG or NO BUG
LINE: <line number where the bug is, or NONE if no bug>
REASON: <one sentence explanation of what specifically is wrong in this code>

File: {file_path}

Code:
{code}"""

    for attempt in range(3):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}]
            )
            text = response.content[0].text.strip()
            verdict = "BUG" if "VERDICT: BUG" in text else "NO BUG"
            line_no = None
            for line in text.splitlines():
                if line.startswith("LINE:"):
                    val = line.replace("LINE:", "").strip()
                    digits = ''.join(filter(str.isdigit, val.split()[0] if val.split() else ''))
                    if digits:
                        line_no = int(digits)
            return verdict, line_no, text
        except anthropic.RateLimitError:
            wait = 120 * (attempt + 1)
            print(f"  Rate limit, waiting {wait}s (attempt {attempt+1}/3)...")
            time.sleep(wait)
        except Exception as e:
            print(f"  Error: {e}")
            return None, None, str(e)
    return None, None, "max retries exceeded"

def classify_bug_found(reported_line, original_bug_line, spm_line, tolerance=5):
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

def process_bug(data_json_path, writer, completed, language, benchmark):
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
            print(f"  Skipping tier {tier_num} for {project}-{bug_id}, already done")
            continue

        code = data.get(code_key)
        if not code:
            print(f"  Skipping tier {tier_num} for {project}-{bug_id} (no code)")
            continue

        print(f"  Running tier {tier_num} for {project}-{bug_id}...")
        verdict, reported_line, full_response = ask_claude(code, file_path, benchmark)

        if verdict is None:
            print(f"  Failed, skipping")
            continue

        correct = verdict == expected
        bug_found = classify_bug_found(reported_line, original_bug_line, spm_line)

        writer.writerow({
            "project": project,
            "bug_id": bug_id,
            "language": language,
            "benchmark": benchmark,
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
        time.sleep(20)

if __name__ == "__main__":
    OUT_CSV = "../../results/v2/results_v2.csv"
    fields = [
        "project", "bug_id", "language", "benchmark", "tier", "expected",
        "verdict", "correct", "reported_line", "original_bug_line",
        "spm_line", "bug_found", "response"
    ]

    completed = load_completed(OUT_CSV)
    print(f"Already completed: {len(completed)} results")

    with open(OUT_CSV, "a", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fields)
        if len(completed) == 0:
            writer.writeheader()

        for bug_dir in JAVA_BUGS:
            data_path = f"../../data/bugs/{bug_dir}/data.json"
            if os.path.exists(data_path):
                print(f"Processing Java {bug_dir}...")
                process_bug(data_path, writer, completed, "java", "Defects4J")
                csvfile.flush()

        for bug_dir in PY_BUGS:
            data_path = f"../../data/pybugs/{bug_dir}/data.json"
            if os.path.exists(data_path):
                print(f"Processing Python {bug_dir}...")
                process_bug(data_path, writer, completed, "python", "BugsInPy")
                csvfile.flush()

    print(f"Done! Results saved to {OUT_CSV}")
