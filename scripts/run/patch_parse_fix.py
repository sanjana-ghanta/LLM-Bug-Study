"""
Patches parse_fix() in both run_experiment_v9_testfix.py and
run_experiment_v9_testfix_math.py, replacing the fragile line-by-line
version with a regex-based one that:
  - works whether or not the response has real line breaks
  - takes the LAST ORIGINAL/FIXED pair, in case Claude reconsiders
    mid-response (see Lang_4)

Run from scripts/run/:
    python3 patch_parse_fix.py
"""

import os
import re

OLD_BLOCK = '''def parse_fix(fix_response):
    original = None
    fixed = None
    for line in fix_response.splitlines():
        if line.startswith('ORIGINAL:'):
            original = line.replace('ORIGINAL:', '').strip()
        elif line.startswith('FIXED:'):
            fixed = line.replace('FIXED:', '').strip()
    return original, fixed'''

NEW_BLOCK = '''import re as _re

def parse_fix(fix_response):
    """
    Regex-based parser (v2). Handles responses with or without real line
    breaks, and takes the LAST ORIGINAL/FIXED pair in the response -- so
    that if Claude reconsiders mid-response (explores multiple candidate
    lines before settling on one), we get its final answer, not its first
    draft.
    """
    if not fix_response:
        return None, None
    pattern = _re.compile(
        r'ORIGINAL:\\s*(.*?)\\s*FIXED:\\s*(.*?)\\s*(?=ORIGINAL:|EXPLANATION:|$)',
        _re.DOTALL
    )
    matches = pattern.findall(fix_response)
    if not matches:
        return None, None
    original, fixed = matches[-1]
    return original.strip(), fixed.strip()'''

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

    changed = False
    backup_written = False

    if OLD_BLOCK in content:
        backup_name = fname + ".bak"
        if not backup_written:
            with open(backup_name, "w") as f:
                f.write(content)
            backup_written = True
        content = content.replace(OLD_BLOCK, NEW_BLOCK)
        changed = True
        print(f"PATCHED (parser): {fname}")
    elif "def parse_fix" in content and "_re.DOTALL" in content:
        print(f"SKIP (parser already patched): {fname}")
    else:
        print(f"WARNING: old parse_fix block not found verbatim in {fname} -- parser not touched, check manually")

    if "max_tokens=256," in content:
        if not backup_written:
            with open(fname + ".bak", "w") as f:
                f.write(content)
            backup_written = True
        content = content.replace("max_tokens=256,", "max_tokens=512,")
        changed = True
        print(f"PATCHED (max_tokens 256->512): {fname}")
    elif "max_tokens=512," in content:
        print(f"SKIP (max_tokens already 512): {fname}")
    else:
        print(f"WARNING: 'max_tokens=256,' not found verbatim in {fname} -- not touched, check manually")

    if changed:
        with open(fname, "w") as f:
            f.write(content)

print("\nDone. Run 'python3 -m py_compile <file>' on each patched file to sanity check.")

