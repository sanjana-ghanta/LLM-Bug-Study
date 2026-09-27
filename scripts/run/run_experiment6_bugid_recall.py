"""
Experiment 6: Bug ID Recall Test -- adapted from the original design
(results/java/Experiment6.md) for GLM/DeepSeek/GPT-OSS instead of Claude.

Two deliberate, disclosed simplifications from the original design:
  - No "hint" field (original source of this field is unknown/unrecoverable)
  - No full project file manifest (many raw checkouts were deleted earlier
    to save disk space; regenerating them is a substantial separate task)
Both were secondary enrichments in the original design, not the core
mechanism being tested (does bug-ID knowledge alone shift behavior toward
retrieval rather than reasoning).

Only runs on bugs a given model got WRONG on Tier 2 in the main five-tier
experiment (see find_tier2_misses.py) -- the interesting question here is
whether direct bug-ID knowledge "unlocks" something raw code alone didn't.

Usage:
    python3 run_experiment6_bugid_recall.py --model glm-5.3-thinking
    python3 run_experiment6_bugid_recall.py --model deepseek-v4-flash-thinking
    python3 run_experiment6_bugid_recall.py --model gpt-oss-thinking
"""

import argparse
import csv
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from lib.llm_clients import call_llm

BASE = os.path.expanduser("~/llm-bug-study/experiment")
BUGS_DIR = os.path.join(BASE, "data/bugs")
RESULTS_DIR = os.path.join(BASE, "results/java")

MAX_TOKENS = 7000
BETWEEN_CALL_SLEEP_SECONDS = 8
RETRY_WAIT_SECONDS = 30

PROMPT_TEMPLATE = """You are analyzing code from the Defects4J benchmark.

This is bug ID {bug_id} from the {project} project in the Defects4J buggy dataset.

Here is the source file:
{file_path}
{source_code}

What line is the bug on?

Please respond in this exact format:
LINE: <line number, or NONE if there is no bug>
REASON: <one sentence explanation of what specifically is wrong>"""


MAX_FILE_LINES = 250  # files longer than this are excluded from Experiment 6
# entirely, rather than windowed -- any window centered on (or near) the
# real bug line would leak its approximate location, since this
# experiment's task is naming an exact line number, unlike the main
# detection task's binary verdict. Sending the whole file is only safe
# (both answer-neutral and token-budget-safe) below this length.


def ask_model(model_key, code, file_path, project, bug_id, center_line=None):
    prompt = PROMPT_TEMPLATE.format(bug_id=bug_id, project=project, file_path=file_path, source_code=code)

    response_text = None
    for attempt in range(3):
        try:
            response_text = call_llm(
                model_key,
                system_prompt="You are a careful code reviewer with knowledge of common software benchmarks.",
                user_prompt=prompt,
                max_tokens=MAX_TOKENS,
            )
        except Exception as e:
            err_str = str(e).lower()
            if "rate limit" in err_str or "429" in err_str:
                print(f"  Rate limit hit, waiting {RETRY_WAIT_SECONDS}s...")
                time.sleep(RETRY_WAIT_SECONDS)
                continue
            else:
                print(f"  Error calling {model_key}: {e}")
                return None

        if response_text:
            break
        if attempt < 2:
            print(f"  Empty response, retrying ({attempt + 1}/2)...")
    else:
        print(f"  WARNING: empty response from {model_key} after 3 attempts")
        return None

    return response_text


def parse_line_number(response_text):
    """Returns an int line number, or None if the model said NONE/gave no
    parseable line."""
    match = re.search(r"LINE:\s*(\d+)", response_text)
    if match:
        return int(match.group(1))
    return None


def classify_tier1(reported_line):
    """Tier 1 = clean/patched code, no bug actually exists."""
    if reported_line is not None:
        return "pattern_matched_clean"  # gave a confident line on bug-free code
    return "reasoned_no_bug_or_malformed"


def classify_tier2(reported_line, actual_line):
    """Tier 2 = the real, buggy code."""
    if reported_line is None:
        return "none"
    if actual_line is not None and abs(reported_line - actual_line) <= 5:
        return "correct"
    return "wrong"


def load_completed(csv_path):
    completed = set()
    if os.path.exists(csv_path):
        with open(csv_path, newline="") as f:
            for row in csv.DictReader(f):
                completed.add((row["project"], row["bug_id"], row["tier"]))
    return completed


def main():
    parser = argparse.ArgumentParser(description="Experiment 6: Bug ID Recall Test")
    parser.add_argument("--model", required=True, help="Model key from lib.config.MODELS")
    args = parser.parse_args()

    misses_path = os.path.join(BASE, f"tier2_misses_java_{args.model}.txt")
    if not os.path.exists(misses_path):
        print(f"No Tier-2-misses file found at {misses_path}. Run find_tier2_misses.py first.")
        sys.exit(1)

    with open(misses_path) as f:
        target_bugs = [line.strip() for line in f if line.strip()]
    print(f"Loaded {len(target_bugs)} Tier-2-missed bugs for {args.model}")

    out_csv = os.path.join(RESULTS_DIR, f"results_exp6_bugid_recall_{args.model}.csv")
    fields = ["project", "bug_id", "tier", "reported_line", "actual_line", "classification", "response"]
    completed = load_completed(out_csv)
    file_has_content = os.path.exists(out_csv) and os.path.getsize(out_csv) > 0

    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(out_csv, "a", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fields)
        if not file_has_content:
            writer.writeheader()

        for bug_dir in target_bugs:
            data_path = os.path.join(BUGS_DIR, bug_dir, "data.json")
            if not os.path.exists(data_path):
                print(f"  Skipping {bug_dir}, no data.json found")
                continue
            with open(data_path) as f:
                data = json.load(f)

            project = data["project"]
            bug_id = str(data["bug_id"])
            file_path = data["file_path"]
            actual_line = data.get("original_bug_line")

            for tier, code_key in [("1", "patched_code"), ("2", "buggy_code")]:
                if (project, bug_id, tier) in completed:
                    print(f"  Skipping tier {tier} for {project}-{bug_id}, already done")
                    continue

                code = data.get(code_key)
                if not code:
                    print(f"  Skipping tier {tier} for {project}-{bug_id} (no code)")
                    continue

                if len(code.splitlines()) > MAX_FILE_LINES:
                    print(f"  Skipping tier {tier} for {project}-{bug_id} "
                          f"(file too large: {len(code.splitlines())} lines, "
                          f"windowing would leak the answer's location)")
                    continue

                print(f"  Running tier {tier} for {project}-{bug_id}...")
                response_text = ask_model(args.model, code, file_path, project, bug_id, actual_line)
                if response_text is None:
                    continue

                reported_line = parse_line_number(response_text)
                if tier == "1":
                    classification = classify_tier1(reported_line)
                else:
                    classification = classify_tier2(reported_line, actual_line)

                writer.writerow({
                    "project": project,
                    "bug_id": bug_id,
                    "tier": tier,
                    "reported_line": reported_line,
                    "actual_line": actual_line,
                    "classification": classification,
                    "response": response_text.replace("\n", " "),
                })
                csvfile.flush()
                time.sleep(BETWEEN_CALL_SLEEP_SECONDS)

    print(f"Done! Results saved to {out_csv}")


if __name__ == "__main__":
    main()

