"""
Experiment 7: Benchmark-Context Framing -- the second follow-up probe
(paper_draft.tex, "Follow-Up Conditional Probes"), a weaker anchoring
signal than Experiment 6 (Bug ID Recall).

Where Experiment 6 tells the model exactly which bug ID and project the
snippet comes from, this probe tells it only that the snippet is drawn
from a well-known, publicly available bug-detection benchmark -- no bug
ID, no project name. The question is whether that vaguer signal alone is
enough to shift behavior toward memorized-pattern recall, or whether
Experiment 6's effect specifically required the precise identifier.

Restricted to each model's own Tier-2 misses, same as Experiment 6 (see
find_tier2_misses.py). Reuses the same two simplifications disclosed
there (no "hint" field, no full project file manifest) and the same
250-line file-size exclusion rule for the same reason: windowing a large
file around the real bug line would leak its approximate location, which
matters here since the task is naming an exact line number.

Usage:
    python3 run_experiment7_context_framing.py --model glm-5.3-thinking
    python3 run_experiment7_context_framing.py --model deepseek-v4-flash-thinking
    python3 run_experiment7_context_framing.py --model gpt-oss-thinking
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

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BUGS_DIR = os.path.join(BASE, "data/bugs")
RESULTS_DIR = os.path.join(BASE, "results/java")

MAX_TOKENS = 7000
REASONING_EFFORT = None  # set from --reasoning-effort
BETWEEN_CALL_SLEEP_SECONDS = 8
RETRY_WAIT_SECONDS = 30

# Deliberately withholds bug_id and project -- that's the entire point of
# this probe relative to Experiment 6. Only the fact that it's benchmark
# code is disclosed.
PROMPT_TEMPLATE = """You are analyzing a source code file that is drawn from a
well-known, publicly available software bug-detection benchmark used in
academic research.

Here is the source file:
{file_path}
{source_code}

What line is the bug on?

Please respond in this exact format:
LINE: <line number, or NONE if there is no bug>
REASON: <one sentence explanation of what specifically is wrong>"""


MAX_FILE_LINES = 1000  # same rationale as Experiment 6: sending the whole
# file is only answer-neutral and token-budget-safe below this length;
# larger files are excluded entirely rather than windowed.


def ask_model(model_key, code, file_path):
    prompt = PROMPT_TEMPLATE.format(file_path=file_path, source_code=code)

    response_text = None
    for attempt in range(3):
        try:
            response_text = call_llm(
                model_key,
                system_prompt="You are a careful code reviewer with knowledge of common software benchmarks.",
                user_prompt=prompt,
                max_tokens=MAX_TOKENS,
                reasoning_effort=REASONING_EFFORT,
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
    parser = argparse.ArgumentParser(description="Experiment 7: Benchmark-Context Framing")
    parser.add_argument("--model", required=True, help="Model key from lib.config.MODELS")
    parser.add_argument("--reasoning-effort", default=None, choices=["low", "medium", "high"],
                        help="Reasoning effort for models that support it")
    args = parser.parse_args()
    global REASONING_EFFORT
    REASONING_EFFORT = args.reasoning_effort

    misses_path = os.path.join(BASE, "results", "tier2_misses", f"tier2_misses_java_{args.model}.txt")
    if not os.path.exists(misses_path):
        print(f"No Tier-2-misses file found at {misses_path}. Run find_tier2_misses.py first.")
        sys.exit(1)

    with open(misses_path) as f:
        target_bugs = [line.strip() for line in f if line.strip()]
    print(f"Loaded {len(target_bugs)} Tier-2-missed bugs for {args.model}")

    out_csv = os.path.join(RESULTS_DIR, f"results_exp7_context_framing_{args.model}.csv")
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
                response_text = ask_model(args.model, code, file_path)
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
