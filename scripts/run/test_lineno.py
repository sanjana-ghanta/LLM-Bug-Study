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
    
    line_no = None
    for line in text.splitlines():
        if line.startswith("LINE:"):
            val = line.replace("LINE:", "").strip()
            if val.isdigit():
                line_no = int(val)
    
    return verdict, line_no, text

def classify_bug_found(reported_line, original_bug_line, spm_line, tolerance=5):
    if reported_line is None:
        return "none"
    if original_bug_line and abs(reported_line - original_bug_line) <= tolerance:
        return "original"
    if spm_line and abs(reported_line - spm_line) <= tolerance:
        return "spm"
    return "other"

def process_bug(data_json_path, language="java"):
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

    print(f"\n{'='*50}")
    print(f"{project}-{bug_id} | original bug line: {original_bug_line}")
    print(f"{'='*50}")

    for tier_num, (code_key, expected, spm_line) in tiers.items():
        code = data.get(code_key)
        if not code:
            continue

        verdict, reported_line, full_response = ask_claude_with_lineno(code, file_path)
        correct = verdict == expected
        bug_found = classify_bug_found(reported_line, original_bug_line, spm_line)

        print(f"  Tier {tier_num}: verdict={verdict} correct={correct} reported_line={reported_line} spm_line={spm_line} bug_found={bug_found}")
        time.sleep(5)

if __name__ == "__main__":
    # Test 5 Java bugs
    java_bugs = ["Lang_1", "Lang_3", "Math_1", "Math_2", "Chart_1"]
    for bug in java_bugs:
        path = f"../../data/bugs/{bug}/data.json"
        if os.path.exists(path):
            process_bug(path, language="java")

    # Test 5 Python bugs
    py_bugs = ["pandas_1", "pandas_2", "black_1", "black_2", "thefuck_2"]
    for bug in py_bugs:
        path = f"../../data/pybugs/{bug}/data.json"
        if os.path.exists(path):
            process_bug(path, language="python")

    print("\nTest done!")
