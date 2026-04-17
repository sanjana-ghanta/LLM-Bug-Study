import re
import json
import os
import time
import csv
import anthropic

client = anthropic.Anthropic()

def truncate_code(code, max_lines=100):
    """Only send first 100 lines to stay under token limits."""
    lines = code.splitlines()
    if len(lines) > max_lines:
        return "\n".join(lines[:max_lines]) + "\n... (truncated)"
    return code

def ask_claude(code, file_path):
    code = truncate_code(code, max_lines=80)
    prompt = f"""Review the following Java code from {file_path} and determine if it contains a bug.
Respond in this exact format:
VERDICT: BUG or NO BUG
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
    return verdict, text

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

    project = data["project"]
    bug_id = str(data["bug_id"])
    file_path = data["file_path"]

    tiers = {
        1: ("patched_code", "NO BUG"),
        2: ("buggy_code", "BUG"),
        3: ("tier3_code", "BUG"),
        4: ("tier4_code", "BUG"),
        5: ("tier5_code", "BUG"),
    }

    for tier_num, (code_key, expected) in tiers.items():
        if (project, bug_id, str(tier_num)) in completed:
            print(f"  Skipping tier {tier_num} for {project}-{bug_id}, already done")
            continue

        code = data.get(code_key)
        if not code:
            print(f"  Skipping tier {tier_num} for {project}-{bug_id} (no code)")
            continue

        print(f"  Running tier {tier_num} for {project}-{bug_id}...")
        try:
            verdict, full_response = ask_claude(code, file_path)
        except anthropic.RateLimitError:
            print("  Rate limit hit, waiting 90 seconds...")
            time.sleep(90)
            verdict, full_response = ask_claude(code, file_path)

        correct = verdict == expected
        writer.writerow({
            "project": project,
            "bug_id": bug_id,
            "tier": tier_num,
            "expected": expected,
            "verdict": verdict,
            "correct": correct,
            "response": full_response.replace("\n", " ")
        })
        time.sleep(20)

if __name__ == "__main__":
    BUGS_DIR = "../../data/bugs"
    OUT_CSV = "../../results/java/results.csv"

    fields = ["project", "bug_id", "tier", "expected", "verdict", "correct", "response"]
    completed = load_completed(OUT_CSV)
    print(f"Already completed: {len(completed)} tier results")

    with open(OUT_CSV, "a", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fields)
        if len(completed) == 0:
            writer.writeheader()

        for bug_dir in sorted(os.listdir(BUGS_DIR)):
            data_path = os.path.join(BUGS_DIR, bug_dir, "data.json")
            if os.path.exists(data_path):
                print(f"Processing {bug_dir}...")
                process_bug(data_path, writer, completed)
                csvfile.flush()

    print(f"Done! Results saved to {OUT_CSV}")
