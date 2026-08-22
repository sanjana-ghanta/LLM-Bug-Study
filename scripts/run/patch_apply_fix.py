"""
Patches apply_fix_to_file() in both test-fix scripts: when original_code's
text matches more than one line in the file, pick whichever match is
CLOSEST to Claude's reported line number, instead of always taking the
first one top-to-bottom.

Run from scripts/run/:
    python3 patch_apply_fix.py
"""

import os

OLD_BLOCK_VARIANT_1 = '''def apply_fix_to_file(full_file_path, original_line, fixed_line):
    with open(full_file_path) as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        if line.strip() == original_line.strip():
            indent = len(line) - len(line.lstrip())
            lines[i] = " " * indent + fixed_line.strip() + "\\n"
            with open(full_file_path, "w") as f:
                f.writelines(lines)
            return True
    return False'''

OLD_BLOCK_VARIANT_2 = '''def apply_fix_to_file(full_file_path, original_line, fixed_line):
    with open(full_file_path) as f:
        lines = f.readlines()
    # try exact match first
    for i, line in enumerate(lines):
        if line.strip() == original_line.strip():
            # preserve original indentation
            indent = len(line) - len(line.lstrip())
            lines[i] = " " * indent + fixed_line.strip() + "\\n"
            with open(full_file_path, "w") as f:
                f.writelines(lines)
            return True
    return False'''

OLD_BLOCKS = [OLD_BLOCK_VARIANT_1, OLD_BLOCK_VARIANT_2]

NEW_BLOCK = '''def apply_fix_to_file(full_file_path, original_line, fixed_line, reported_line=None):
    """
    Finds the line matching original_line's text and replaces it with
    fixed_line. If the text appears more than once in the file, picks the
    occurrence CLOSEST to reported_line (Claude's self-reported line
    number) instead of always taking the first match -- since always
    taking the first match can silently edit the wrong copy of duplicated
    code (confirmed cause of several bad-outcome bugs in Experiment 9).
    """
    with open(full_file_path) as f:
        lines = f.readlines()

    match_indices = [i for i, line in enumerate(lines) if line.strip() == original_line.strip()]
    if not match_indices:
        return False

    if len(match_indices) == 1 or reported_line is None:
        i = match_indices[0]
    else:
        # pick whichever match is closest to Claude's reported line (1-indexed)
        i = min(match_indices, key=lambda idx: abs((idx + 1) - reported_line))

    indent = len(lines[i]) - len(lines[i].lstrip())
    lines[i] = " " * indent + fixed_line.strip() + "\\n"
    with open(full_file_path, "w") as f:
        f.writelines(lines)
    return True'''

TARGET_FILES = [
    "run_experiment_v9_testfix.py",
    "run_experiment_v9_testfix_math.py",
]

for fname in TARGET_FILES:
    if not os.path.exists(fname):
        print(f"SKIP: {fname} not found in current directory")
        continue
    with open(fname) as f:
        content = f.read()

    matched_block = None
    for block in OLD_BLOCKS:
        if block in content:
            matched_block = block
            break

    if matched_block:
        with open(fname + ".bak2", "w") as f:
            f.write(content)
        content = content.replace(matched_block, NEW_BLOCK)
        with open(fname, "w") as f:
            f.write(content)
        print(f"PATCHED: {fname} (backup saved as {fname}.bak2)")
    elif "reported_line=None" in content:
        print(f"SKIP: {fname} already patched")
    else:
        print(f"WARNING: old apply_fix_to_file block not found verbatim in {fname} -- not touched, check manually")

print("\nNote: existing calls to apply_fix_to_file(...) in the rest of each script")
print("still work unchanged (reported_line defaults to None = old first-match")
print("behavior). To actually use the new tie-break logic on future runs, pass")
print("claude_line as the 4th argument wherever apply_fix_to_file is called.")

