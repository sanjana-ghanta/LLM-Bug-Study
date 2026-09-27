"""
Core, reusable pipeline functions. Every experiment script should import
from here instead of redefining its own copy of checkout/apply-fix/test-
capture logic -- consolidating these in one place is what let us find and
fix the parse_fix, max_tokens, line-number-mismatch, and duplicate-text
bugs discovered during the original per-script-copy version of this
pipeline, and is what will prevent the same class of bug from silently
reappearing in a new copy-pasted script.
"""

import os
import re
import json
import shutil
import subprocess
import xml.etree.ElementTree as ET

from lib.config import PROJECTS, BUGS_DIR


def checkout_bug(project, bug_id, target_dir):
    """Fresh defects4j checkout of the buggy version of a bug into target_dir."""
    if project not in PROJECTS:
        raise ValueError(f"Unknown project '{project}'. Known: {list(PROJECTS.keys())}")
    defects4j_name = PROJECTS[project]["defects4j_name"]
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir)
    result = subprocess.run(
        ['defects4j', 'checkout', '-p', defects4j_name, '-v', f'{bug_id}b', '-w', target_dir],
        capture_output=True, text=True, timeout=120
    )
    return os.path.exists(target_dir)


def get_bug_metadata(project, bug_id):
    """Reads data.json for a bug: returns dict with at least 'file_path'."""
    data_path = os.path.join(BUGS_DIR, f"{project}_{bug_id}", "data.json")
    if not os.path.exists(data_path):
        return None
    with open(data_path) as f:
        return json.load(f)


def find_source_file(tmp_dir, file_path, project):
    """Locates file_path inside a checkout, trying each of the project's
    configured src_candidates prefixes in order."""
    src_candidates = PROJECTS[project]["src_candidates"]
    for src in src_candidates:
        candidate = os.path.join(tmp_dir, src, file_path) if src else os.path.join(tmp_dir, file_path)
        if os.path.exists(candidate):
            return candidate
    return None


def find_all_occurrences(full_file_path, target_text):
    """Returns every 1-indexed line number where the stripped line content
    exactly matches target_text. Used to detect duplicate-text ambiguity
    before applying a fix -- see apply_fix_to_file."""
    if not target_text:
        return []
    with open(full_file_path) as f:
        lines = f.readlines()
    return [i + 1 for i, line in enumerate(lines) if line.strip() == target_text.strip()]


def apply_fix_to_file(full_file_path, original_line, fixed_line, reported_line=None):
    """
    Replaces the line matching original_line's text with fixed_line.
    If original_line's text matches MORE THAN ONE line in the file, picks
    whichever occurrence is CLOSEST to reported_line (the model's
    self-reported line number) rather than always the first match --
    confirmed necessary after finding 8/50 bugs where "always take the
    first match" silently edited the wrong copy of duplicated code.

    Returns (applied: bool, actual_line_edited: int | None, was_ambiguous: bool).
    """
    with open(full_file_path) as f:
        lines = f.readlines()

    match_indices = [i for i, line in enumerate(lines) if line.strip() == original_line.strip()]
    if not match_indices:
        return False, None, False

    was_ambiguous = len(match_indices) > 1
    if not was_ambiguous or reported_line is None:
        chosen_idx = match_indices[0]
    else:
        chosen_idx = min(match_indices, key=lambda idx: abs((idx + 1) - reported_line))

    indent = len(lines[chosen_idx]) - len(lines[chosen_idx].lstrip())
    lines[chosen_idx] = " " * indent + fixed_line.strip() + "\n"
    with open(full_file_path, "w") as f:
        f.writelines(lines)
    return True, chosen_idx + 1, was_ambiguous


def parse_fix(fix_response):
    """
    Extracts (original_code, fixed_code) from a model's raw ORIGINAL:/
    FIXED:/EXPLANATION: response. Uses the LAST matching pair in the
    response (not the first), and doesn't depend on real line breaks being
    present -- both fixes for real failure modes found in this pipeline
    (a model reconsidering mid-response, and single-line responses with no
    literal newlines).
    """
    if not fix_response:
        return None, None
    pattern = re.compile(
        r'ORIGINAL:\s*(.*?)\s*FIXED:\s*(.*?)\s*(?=ORIGINAL:|EXPLANATION:|$)',
        re.DOTALL
    )
    matches = pattern.findall(fix_response)
    if not matches:
        return None, None
    original, fixed = matches[-1]
    return original.strip(), fixed.strip()


def capture_failing_tests(checkout_dir):
    """Runs defects4j test and returns the SET of failing test names
    (ClassName::methodName), not just a count."""
    result = subprocess.run(
        ['defects4j', 'test', '-w', checkout_dir],
        capture_output=True, text=True, timeout=300
    )
    output = result.stdout + result.stderr
    names = set()
    failing_tests_path = os.path.join(checkout_dir, 'failing_tests')
    if os.path.exists(failing_tests_path):
        with open(failing_tests_path) as f:
            content = f.read()
        names = set(re.findall(r'--- (\S+)', content))
    if not names:
        names = set(re.findall(r'^\s*-\s+(\S+)', output, re.MULTILINE))
    return names


def run_coverage(checkout_dir):
    """Runs defects4j coverage; returns the path to coverage.xml, or None."""
    subprocess.run(
        ['defects4j', 'coverage', '-w', checkout_dir],
        capture_output=True, text=True, timeout=600
    )
    xml_path = os.path.join(checkout_dir, 'coverage.xml')
    return xml_path if os.path.exists(xml_path) else None


def get_line_hits(xml_path, filename_contains, lineno):
    """Looks up the hit count for a specific line number in coverage.xml."""
    if not xml_path or not os.path.exists(xml_path) or lineno is None:
        return None
    tree = ET.parse(xml_path)
    root = tree.getroot()
    for cls in root.findall('.//class'):
        if filename_contains in cls.get('filename', ''):
            for line in cls.findall('.//line'):
                if int(line.get('number')) == lineno:
                    return int(line.get('hits', 0))
    return None


def find_real_line_number(full_file_path, target_text):
    """Returns the FIRST line number where target_text's exact content
    lives, or None. For unambiguous (non-duplicated) text this is reliable;
    for duplicated text, prefer find_all_occurrences + your own tie-break
    logic instead of this function."""
    occurrences = find_all_occurrences(full_file_path, target_text)
    return occurrences[0] if occurrences else None

