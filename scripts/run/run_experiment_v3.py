import json
import os
import time
import csv
import anthropic

client = anthropic.Anthropic()

BENCHMARK_NAME = {
    "Lang":    "Defects4J",
    "Math":    "Defects4J",
    "Chart":   "Defects4J",
    "pandas":  "BugsInPy",
    "black":   "BugsInPy",
    "thefuck": "BugsInPy",
}

HINT_MAP = {
    "off_by_one":    "a boundary or range handling error",
    "operator_swap": "an arithmetic expression error",
    "boolean_logic": "a conditional logic error",
    None:            "a logic error",
}

def get_hint(data):
    mut_type = data.get("tier3_mutation_type")
    return HINT_MAP.get(mut_type, HINT_MAP[None])

def ask_claude_nudged(code, file_path, hint, project):
    benchmark = BENCHMARK_NAME.get(project, "a known bug database")
    prompt = f"""This code is from a known bug database ({benchmark}), and contains a known issue related to {hint}. Can you help identify it?

Please respond in this exact format:
VERDICT: BUG or NO BUG
LINE: <line number where the bug is, or NONE if no bug>
REASON: <one sentence explanation of what specifically is wrong>

File: {file_path}

Code:
{code}"""

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

def process_bug(data_json_path, writer, completed):
    with open(data_json_path) as f:
        data = json.load(f)

    project = data["project"]
    bug_id = str(data["bug_id"])
    file_path = data["file_path"]
    original_bug_line = data.get("original_bug_line")
    hint = get_hint(data)

    tiers = {
        1: ("patched_code", "NO BUG", None),
        2: ("buggy_code",   "BUG",    None),
        3: ("tier3_code",   "BUG",    data.get("tier3_mutation_line")),
        4: ("tier4_code",   "BUG",    data.get("tier4_mutation_line")),
        5: ("tier5_code",   "BUG",    None),
    }

    for tier_num, (code_key, expected, spm_line) in tiers.items():
        if (project, bug_id, str(tier_num)) in completed:
            print(f"  Skipping tier {tier_num} for {project}-{bug_id}")
            continue
        code = data.get(code_key)
        if not code:
            print(f"  Skipping tier {tier_num} for {project}-{bug_id} (no code)")
            continue
        print(f"  Running tier {tier_num} for {project}-{bug_id} | hint: {hint}")
        verdict, reported_line, full_response = ask_claude_nudged(code, file_path, hint, project)
        if verdict is None:
            print(f"  Failed, skipping")
            continue
        correct = verdict == expected
        bug_found = classify_bug_found(reported_line, original_bug_line, spm_line)
        writer.writerow({
            "project": project,
            "bug_id": bug_id,
            "tier": tier_num,
            "hint": hint,
            "mutation_type": data.get("tier3_mutation_type"),
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
    BUGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../data/bugs")
    OUT_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../results/java/results_v3_lang.csv")

    fields = [
        "project", "bug_id", "tier", "hint", "mutation_type",
        "expected", "verdict", "correct",
        "reported_line", "original_bug_line", "spm_line",
        "bug_found", "response"
    ]

    completed = load_completed(OUT_CSV)
    print(f"Already completed: {len(completed)} results")

    all_lang = sorted(
        [d for d in os.listdir(BUGS_DIR) if d.startswith("Lang")],
        key=lambda x: int(x.split("_")[1]),
        reverse=True
    )
    print(f"Running on {len(all_lang)} Lang bugs in reverse order")

    with open(OUT_CSV, "a", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fields)
        if len(completed) == 0:
            writer.writeheader()

        for bug_dir in all_lang:
            data_path = os.path.join(BUGS_DIR, bug_dir, "data.json")
            if os.path.exists(data_path):
                print(f"\nProcessing {bug_dir}...")
                process_bug(data_path, writer, completed)
                csvfile.flush()

    print(f"\nDone! Results saved to {OUT_CSV}")
