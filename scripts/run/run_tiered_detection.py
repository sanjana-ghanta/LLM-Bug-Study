"""
Experiment 1 (tiered detection), generalized: runs any model in
lib.config.MODELS against any/all projects, instead of one hardcoded
Claude-only script per project.

Usage:
    python3 run_tiered_detection.py --model claude
    python3 run_tiered_detection.py --model glm-5.3-thinking --project Chart
    python3 run_tiered_detection.py --model gpt-oss-thinking --project Lang,Math

Each (project, bug_id, tier, model) combination writes to its own results
file: results_fivetier_<model_key>.csv -- so different models' runs never
collide, and you can compare them side by side afterward.
"""

import argparse
import csv
import json
import os
import sys
import time

# lib/ lives one directory up from scripts/run/ -- add scripts/ to the path
# so `from lib...` imports work regardless of which directory this is run from.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from lib.config import PROJECTS, BUGS_DIR, RESULTS_DIR
from lib.llm_clients import call_llm

# Thinking/reasoning models spend part of their token budget on internal
# reasoning before the final answer -- give real headroom, not the 256 the
# original Claude-only version used (confirmed necessary: see the earlier
# smoke test where gpt-oss-thinking returned an empty response at
# max_tokens=16).
MAX_TOKENS = 7000
RETRY_WAIT_SECONDS = 90
BETWEEN_CALL_SLEEP_SECONDS = 20

TIERS = {
    # tier_num: (code_key, expected_verdict, line_field)
    1: ("patched_code", "NO BUG", "original_bug_line"),
    2: ("buggy_code", "BUG", "original_bug_line"),
    3: ("tier3_code", "BUG", "tier3_mutation_line"),
    5: (None, "BUG", None),  # special-cased below: reads tier5_code_by_model[model_key]
}
# Tier 3 only runs if this bug's Tier 1 already succeeded; Tier 5 only runs
# if this bug's Tier 2 already succeeded -- matches Gulzar's revised 4-tier
# design, and avoids spending calls on tiers whose result would be
# excluded from the conditional analysis anyway. Tier 4 (real+synthetic
# stacked) is dropped entirely -- it isn't part of the revised design.
CONDITIONAL_ON = {"3": "1", "5": "2"}


def truncate_code(code, max_lines=80):
    """Fallback for cases with no known line number: first N lines only."""
    lines = code.splitlines()
    if len(lines) > max_lines:
        return "\n".join(lines[:max_lines]) + "\n... (truncated)"
    return code


def window_code(code, center_line, window=60):
    """
    Returns a slice of code centered on center_line (1-indexed), +/- window
    lines each side, with a line-number prefix on each line so the model
    can still refer to specific lines meaningfully. Falls back to
    truncate_code's simple first-N-lines behavior if center_line is
    unknown (None), and returns the whole snippet unmodified if it's
    already short enough that windowing isn't needed.

    This replaces blindly sending the first 80 lines of a file, which for
    large files (e.g. Chart_1's 1994-line buggy_code, with the real bug at
    line 1797) meant the model was never shown the actual buggy code at all.
    """
    lines = code.splitlines()
    if len(lines) <= 2 * window:
        return code  # short enough to send whole
    if center_line is None:
        return truncate_code(code, max_lines=2 * window)

    start = max(0, center_line - window - 1)
    end = min(len(lines), center_line + window)
    snippet_lines = lines[start:end]
    numbered = [f"{start + i + 1}: {line}" for i, line in enumerate(snippet_lines)]
    header = f"... (showing lines {start + 1}-{end} of {len(lines)}) ...\n"
    return header + "\n".join(numbered)


def ask_model(model_key, code, file_path, center_line=None, reasoning_effort=None, empty_response_retries=2):
    code = window_code(code, center_line)
    prompt = f"""Review the following Java code from {file_path} and determine if it contains a bug.
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
                reasoning_effort=reasoning_effort,
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
            break  # got a real response, stop retrying

        if attempt < empty_response_retries:
            print(f"  Empty response, retrying ({attempt + 1}/{empty_response_retries})...")
        else:
            print(f"  WARNING: empty response from {model_key} after "
                  f"{empty_response_retries + 1} attempts "
                  f"(if this is a thinking model, it may have exhausted its "
                  f"token budget on reasoning -- consider raising MAX_TOKENS)")
            return None, None

    verdict = "BUG" if "VERDICT: BUG" in response_text else "NO BUG"
    return verdict, response_text


def load_completed(csv_path):
    """Returns completed as a set of (project, bug_id, tier) tuples (as
    before), plus correctness as a dict of the same key -> bool, so the
    conditional gate can check whether a bug's baseline tier succeeded
    even if that tier was completed in an earlier session/run."""
    completed = set()
    correctness = {}
    if os.path.exists(csv_path):
        with open(csv_path, newline="") as f:
            for row in csv.DictReader(f):
                key = (row["project"], row["bug_id"], row["tier"])
                completed.add(key)
                correctness[key] = row["correct"] in ("True", "true")
    return completed, correctness


MAX_FAILURE_ATTEMPTS = 3  # after this many failed attempts (across restarts),
                           # stop retrying and skip permanently


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


def process_bug(model_key, data_json_path, writer, completed, correctness,
                 failure_counts, failures_path, reasoning_effort=None):
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
                # baseline tier either hasn't run yet or was answered
                # incorrectly -- skip this call entirely, no row written,
                # matching the conditional design (this result would be
                # excluded from the conditional analysis anyway)
                print(f"  Skipping tier {tier_num} for {project}-{bug_id} "
                      f"(conditional: Tier {baseline_tier} not yet correct)")
                continue

        code = data.get(code_key) if code_key else None
        if tier_num == 5:
            # tier 5 uses GLM's rewrite for ALL models being tested, not a
            # per-model rewrite -- a deliberate choice to run tier5
            # generation only once (rather than once per model), accepting
            # a known trade-off: GLM may have a slight recognition
            # advantage on its own disguise, since DeepSeek/GPT-OSS are
            # being tested on someone else's rewrite. Noted as a paper
            # limitation rather than a design flaw.
            code = data.get("tier5_code_by_model", {}).get("glm-5.3-thinking")
            if code is None:
                # fall back to the old shared field if GLM's rewrite isn't
                # generated yet for this bug, so existing data still works
                code = data.get("tier5_code")

        if not code:
            print(f"  Skipping tier {tier_num} for {project}-{bug_id} (no code)")
            continue

        center_line = data.get(line_field) if line_field else None

        print(f"  [{model_key}] Running tier {tier_num} for {project}-{bug_id} "
              f"(centered on line {center_line})...")
        verdict, full_response = ask_model(model_key, code, file_path, center_line, reasoning_effort)
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
        # keep correctness up to date within THIS run too, so a later tier
        # for the same bug in the same pass sees it immediately
        correctness[(project, bug_id, tier_str)] = correct
        # a successful call clears any prior failure count for this key
        if fkey in failure_counts:
            del failure_counts[fkey]
            save_failure_counts(failures_path, failure_counts)
        time.sleep(BETWEEN_CALL_SLEEP_SECONDS)





def get_all_projects_in_data(bugs_dir):
    """Scans BUGS_DIR for actual project names present, instead of relying
    on lib.config.PROJECTS (which is only needed for live-checkout metadata
    that this script -- reading purely from data.json -- doesn't use)."""
    projects = set()
    for bug_dir in os.listdir(bugs_dir):
        data_path = os.path.join(bugs_dir, bug_dir, "data.json")
        if os.path.exists(data_path):
            with open(data_path) as f:
                data = json.load(f)
            projects.add(data.get("project", bug_dir.split("_")[0]))
    return projects


def main():
    parser = argparse.ArgumentParser(description="Run tiered-detection experiment against any model/project")
    parser.add_argument("--model", required=True, help="Model key from lib.config.MODELS (e.g. claude, glm-5.3-thinking)")
    parser.add_argument("--project", default="all",
                         help="Comma-separated project names (e.g. Chart,Lang) or 'all' (default)")
    parser.add_argument("--reasoning-effort", default=None, choices=["low", "medium", "high"],
                         help="Optional: low/medium/high. Only meaningful for VT ARC models that "
                              "support it; ignored for Claude. Lower effort trades reasoning depth "
                              "for reliability/speed on models with a high empty-response rate.")
    args = parser.parse_args()

    all_projects_in_data = get_all_projects_in_data(BUGS_DIR)

    if args.project == "all":
        wanted_projects = all_projects_in_data
    else:
        wanted_projects = set(args.project.split(","))
        unknown = wanted_projects - all_projects_in_data
        if unknown:
            raise ValueError(f"Unknown project(s): {unknown}. Found in data: {sorted(all_projects_in_data)}")

    out_csv = os.path.join(RESULTS_DIR, f"results_fivetier_{args.model}.csv")
    failures_path = os.path.join(RESULTS_DIR, f"results_fivetier_{args.model}_failures.json")
    fields = ["project", "bug_id", "tier", "expected", "verdict", "correct", "response"]
    completed, correctness = load_completed(out_csv)
    failure_counts = load_failure_counts(failures_path)
    print(f"Model: {args.model} | Projects: {sorted(wanted_projects)} | reasoning_effort: {args.reasoning_effort}")
    print(f"Already completed: {len(completed)} tier results")
    if failure_counts:
        gave_up = sum(1 for c in failure_counts.values() if c >= MAX_FAILURE_ATTEMPTS)
        print(f"Tracking {len(failure_counts)} previously-failed attempts "
              f"({gave_up} permanently given up on after {MAX_FAILURE_ATTEMPTS} tries)")

    # Decide whether to write a header based on whether the file already has
    # content, NOT on the parsed `completed` count -- these can disagree
    # (e.g. if load_completed hits a transient read issue), and doing it
    # this way avoids a duplicate header row corrupting the CSV.
    file_has_content = os.path.exists(out_csv) and os.path.getsize(out_csv) > 0

    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(out_csv, "a", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fields)
        if not file_has_content:
            writer.writeheader()

        for bug_dir in sorted(os.listdir(BUGS_DIR)):
            bug_project = bug_dir.split("_")[0]
            if bug_project not in wanted_projects:
                continue
            data_path = os.path.join(BUGS_DIR, bug_dir, "data.json")
            if os.path.exists(data_path):
                print(f"Processing {bug_dir}...")
                process_bug(args.model, data_path, writer, completed, correctness,
                            failure_counts, failures_path, args.reasoning_effort)
                csvfile.flush()

    print(f"Done! Results saved to {out_csv}")


if __name__ == "__main__":
    main()

