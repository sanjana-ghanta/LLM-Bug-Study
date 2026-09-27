"""
Inspect one bug's tiered-detection results in detail: for each tier, shows
the exact code window that was sent to the model, next to what the model
actually said. Lets you sanity-check results yourself as they come in,
rather than waiting for a full run to trust the summary numbers.

Usage:
    python3 inspect_bug_results.py Chart 16 glm-5.3-thinking
"""

import sys
import os
import csv
import json

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from lib.config import BUGS_DIR, RESULTS_DIR

TIERS = {
    "1": ("patched_code", "NO BUG", "original_bug_line"),
    "2": ("buggy_code", "BUG", "original_bug_line"),
    "3": ("tier3_code", "BUG", "tier3_mutation_line"),
    "4": ("tier4_code", "BUG", "tier4_mutation_line"),
    "5": ("tier5_code", "BUG", None),
}


def window_code(code, center_line, window=60):
    """Same logic as run_tiered_detection.py's window_code -- reproduced
    here so this stays a standalone read-only inspection tool."""
    lines = code.splitlines()
    if len(lines) <= 2 * window:
        return code
    if center_line is None:
        lines_trunc = lines[:2 * window]
        return "\n".join(lines_trunc) + "\n... (truncated)"
    start = max(0, center_line - window - 1)
    end = min(len(lines), center_line + window)
    snippet_lines = lines[start:end]
    numbered = [f"{start + i + 1}: {line}" for i, line in enumerate(snippet_lines)]
    header = f"... (showing lines {start + 1}-{end} of {len(lines)}) ...\n"
    return header + "\n".join(numbered)


def main():
    if len(sys.argv) < 4:
        print("Usage: python3 inspect_bug_results.py <Project> <BugID> <model_key>")
        print("Example: python3 inspect_bug_results.py Chart 16 glm-5.3-thinking")
        sys.exit(1)

    project, bug_id, model_key = sys.argv[1], sys.argv[2], sys.argv[3]

    data_path = os.path.join(BUGS_DIR, f"{project}_{bug_id}", "data.json")
    if not os.path.exists(data_path):
        print(f"No data.json found for {project}_{bug_id}")
        sys.exit(1)
    with open(data_path) as f:
        data = json.load(f)

    results_path = os.path.join(RESULTS_DIR, f"results_fivetier_{model_key}.csv")
    results_by_tier = {}
    if os.path.exists(results_path):
        with open(results_path) as f:
            for row in csv.DictReader(f):
                if row["project"] == project and row["bug_id"] == bug_id:
                    results_by_tier[row["tier"]] = row

    print(f"{'='*70}")
    print(f"=== {project}_{bug_id} | model: {model_key} ===")
    print(f"{'='*70}")

    for tier_num, (code_key, expected, line_field) in TIERS.items():
        code = data.get(code_key)
        center_line = data.get(line_field) if line_field else None
        result = results_by_tier.get(tier_num)

        print(f"\n--- Tier {tier_num} (expected: {expected}, center line: {center_line}) ---")

        if code is None:
            print("  No code stored for this tier.")
        else:
            windowed = window_code(code, center_line)
            windowed_lines = windowed.splitlines()
            print(f"  Code sent ({len(code.splitlines())} total lines in file):")
            if center_line is not None and len(windowed_lines) > 15:
                # show a slice actually centered on the bug line, not just the top
                mid = len(windowed_lines) // 2
                show_start = max(0, mid - 7)
                show_end = min(len(windowed_lines), mid + 8)
                if show_start > 0:
                    print(f"    ... ({show_start} earlier lines not shown here) ...")
                for line in windowed_lines[show_start:show_end]:
                    print(f"    {line}")
                if show_end < len(windowed_lines):
                    print(f"    ... ({len(windowed_lines) - show_end} more lines not shown here) ...")
            else:
                for line in windowed_lines[:15]:
                    print(f"    {line}")
                if len(windowed_lines) > 15:
                    print(f"    ... ({len(windowed_lines) - 15} more lines shown to model, truncated here for display)")

        if result:
            match = "✓" if result["correct"] in ("True", "true") else "✗"
            print(f"\n  {match} Verdict: {result['verdict']}  |  Correct: {result['correct']}")
            print(f"  Response: {result['response']}")
        else:
            print("\n  (No result yet for this tier -- not run, or still in progress)")

    print(f"\n{'='*70}")


if __name__ == "__main__":
    main()

