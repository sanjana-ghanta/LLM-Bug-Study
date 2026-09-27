"""
Python-language equivalent of run_tiered_detection.py. Same tier structure
and same windowing fix applied FROM THE START (the original
run_experiment_python.py had the identical 50-line-truncation flaw as the
Java version -- this version never has that bug in the first place).

Unlike the Java pipeline, this experiment only ever reads pre-extracted
code from data.json -- no live checkout needed -- so there's no PROJECTS
registry dependency here; --project just filters on whatever project name
strings are already present in the data (e.g. pandas, black, thefuck).

Usage:
    python3 run_tiered_detection_python.py --model claude
    python3 run_tiered_detection_python.py --model glm-5.3-thinking --project pandas
"""

import argparse
import csv
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from lib.llm_clients import call_llm

BASE = os.path.expanduser("~/llm-bug-study/experiment")
BUGS_DIR = os.path.join(BASE, "data/pybugs")
RESULTS_DIR = os.path.join(BASE, "results/python")

MAX_TOKENS = 1024
RETRY_WAIT_SECONDS = 90
BETWEEN_CALL_SLEEP_SECONDS = 20

TIERS = {
    1: ("patched_code", "NO BUG", "original_bug_line"),
    2: ("buggy_code", "BUG", "original_bug_line"),
    3: ("tier3_code", "BUG", "tier3_mutation_line"),
    5: (None, "BUG", None),  # special-cased below: reads tier5_code_by_model["glm-5.3-thinking"]
}
# Tier 3 only runs if this bug's Tier 1 already succeeded; Tier 5 only runs
# if this bug's Tier 2 already succeeded -- see Java pipeline for full
# rationale. Tier 4 dropped entirely, not part of the revised design.
CONDITIONAL_ON = {"3": "1", "5": "2"}


def truncate_code(code, max_lines=80):
    lines = code.splitlines()
    if len(lines) > max_lines:
        return "\n".join(lines[:max_lines]) + "\n... (truncated)"
    return code


def window_code(code, center_line, window=60):
    lines = code.splitlines()
    if len(lines) <= 2 * window:
        return code
    if center_line is None:
        return truncate_code(code, max_lines=2 * window)
    start = max(0, center_line - window - 1)
    end = min(len(lines), center_line + window)
    snippet_lines = lines[start:end]
    numbered = [f"{start + i + 1}: {line}" for i, line in enumerate(snippet_lines)]
    header = f"... (showing lines {start + 1}-{end} of {len(lines)}) ...\n"
    return header + "\n".join(numbered)


def ask_model(model_key, code, file_path, center_line=None, empty_response_retries=2):
    code = window_code(code, center_line)
    prompt = f"""Review the following Python code from {file_path} and determine if it contains a bug.
Respond in this exact format:
VERDICT: BUG or NO BUG
REASON: <one sentence explanation>

Code:
{code}"""

    response_text = None
    for attempt in range(empty_response_retries + 1):
        try:
            response_text = call_llm(
                model_key,
                system_prompt="You are a careful code reviewer.",
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
                return None, None

        if response_text:
            break

        if attempt < empty_response_retries:
            print(f"  Empty response, retrying ({attempt + 1}/{empty_response_retries})...")
        else:
            print(f"  WARNING: empty response from {model_key} after "
                  f"{empty_response_retries + 1} attempts")
            return None, None

    if not response_text:
        print(f"  WARNING: empty response from {model_key} "
              f"(thinking model may have exhausted its token budget on reasoning)")
        return None, None

    verdict = "BUG" if "VERDICT: BUG" in response_text else "NO BUG"
    return verdict, response_text


def load_completed(csv_path):
    completed = set()
    correctness = {}
    if os.path.exists(csv_path):
        with open(csv_path, newline="") as f:
            for row in csv.DictReader(f):
                key = (row["project"], row["bug_id"], row["tier"])
                completed.add(key)
                correctness[key] = row["correct"] in ("True", "true")
    return completed, correctness


MAX_FAILURE_ATTEMPTS = 3


def load_failure_counts(failures_path):
    if os.path.exists(failures_path):
        with open(failures_path) as f:
            return json.load(f)
    return {}


def save_failure_counts(failures_path, failure_counts):
    with open(failures_path, "w") as f:
        json.dump(failure_counts, f, indent=2)


def failure_key(project, bug_id, tier_str):
    return f"{project}|{bug_id}|{tier_str}"


def process_bug(model_key, data_json_path, writer, completed, correctness, failure_counts, failures_path):
    with open(data_json_path) as f:
        data = json.load(f)

    project = data["project"]
    bug_id = str(data["bug_id"])
    file_path = data["file_path"]

    for tier_num, (code_key, expected, line_field) in TIERS.items():
        tier_str = str(tier_num)
        if (project, bug_id, tier_str) in completed:
            print(f"  Skipping tier {tier_num} for {project}-{bug_id}, already done")
            continue

        fkey = failure_key(project, bug_id, tier_str)
        prior_failures = failure_counts.get(fkey, 0)
        if prior_failures >= MAX_FAILURE_ATTEMPTS:
            print(f"  Skipping tier {tier_num} for {project}-{bug_id} "
                  f"(gave up after {prior_failures} failed attempts)")
            continue

        baseline_tier = CONDITIONAL_ON.get(tier_str)
        if baseline_tier is not None:
            baseline_key = (project, bug_id, baseline_tier)
            if not correctness.get(baseline_key):
                print(f"  Skipping tier {tier_num} for {project}-{bug_id} "
                      f"(conditional: Tier {baseline_tier} not yet correct)")
                continue

        code = data.get(code_key) if code_key else None
        if tier_num == 5:
            # tier 5 uses GLM's shared disguise for ALL models being
            # tested (see Java pipeline for the full rationale), not the
            # old flat tier5_code field from the original single-model run.
            code = data.get("tier5_code_by_model", {}).get("glm-5.3-thinking")
            if code is None:
                # fall back to the old shared field only if GLM's rewrite
                # isn't generated yet for this specific bug
                code = data.get("tier5_code")

        if not code:
            print(f"  Skipping tier {tier_num} for {project}-{bug_id} (no code)")
            continue

        center_line = data.get(line_field) if line_field else None

        print(f"  [{model_key}] Running tier {tier_num} for {project}-{bug_id} "
              f"(centered on line {center_line})...")
        verdict, full_response = ask_model(model_key, code, file_path, center_line)
        if verdict is None:
            new_count = prior_failures + 1
            failure_counts[fkey] = new_count
            save_failure_counts(failures_path, failure_counts)
            remaining = MAX_FAILURE_ATTEMPTS - new_count
            print(f"  Skipping tier {tier_num} for {project}-{bug_id} "
                  f"(call failed -- attempt {new_count}/{MAX_FAILURE_ATTEMPTS}, "
                  f"{remaining} retries left before giving up)")
            continue

        correct = verdict == expected
        writer.writerow({
            "project": project,
            "bug_id": bug_id,
            "tier": tier_num,
            "expected": expected,
            "verdict": verdict,
            "correct": correct,
            "response": full_response.replace("\n", " "),
        })
        correctness[(project, bug_id, tier_str)] = correct
        if fkey in failure_counts:
            del failure_counts[fkey]
            save_failure_counts(failures_path, failure_counts)
        time.sleep(BETWEEN_CALL_SLEEP_SECONDS)


def main():
    parser = argparse.ArgumentParser(description="Run Python tiered-detection experiment against any model")
    parser.add_argument("--model", required=True, help="Model key from lib.config.MODELS")
    parser.add_argument("--project", default="all",
                         help="Comma-separated project names (e.g. pandas,black) or 'all' (default)")
    args = parser.parse_args()

    wanted_projects = None if args.project == "all" else set(args.project.split(","))

    out_csv = os.path.join(RESULTS_DIR, f"results_fivetier_python_{args.model}.csv")
    failures_path = os.path.join(RESULTS_DIR, f"results_fivetier_python_{args.model}_failures.json")
    fields = ["project", "bug_id", "tier", "expected", "verdict", "correct", "response"]
    completed, correctness = load_completed(out_csv)
    failure_counts = load_failure_counts(failures_path)
    print(f"Model: {args.model} | Projects: {wanted_projects or 'all'}")
    print(f"Already completed: {len(completed)} tier results")
    if failure_counts:
        gave_up = sum(1 for c in failure_counts.values() if c >= MAX_FAILURE_ATTEMPTS)
        print(f"Tracking {len(failure_counts)} previously-failed attempts "
              f"({gave_up} permanently given up on after {MAX_FAILURE_ATTEMPTS} tries)")

    file_has_content = os.path.exists(out_csv) and os.path.getsize(out_csv) > 0

    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(out_csv, "a", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fields)
        if not file_has_content:
            writer.writeheader()

        for bug_dir in sorted(os.listdir(BUGS_DIR)):
            data_path = os.path.join(BUGS_DIR, bug_dir, "data.json")
            if not os.path.exists(data_path):
                continue
            if wanted_projects is not None:
                with open(data_path) as f:
                    bug_project = json.load(f).get("project")
                if bug_project not in wanted_projects:
                    continue
            print(f"Processing {bug_dir}...")
            process_bug(args.model, data_path, writer, completed, correctness, failure_counts, failures_path)
            csvfile.flush()

    print(f"Done! Results saved to {out_csv}")


if __name__ == "__main__":
    main()

