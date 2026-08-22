"""
Diagnostic for the 2 unresolved coverage contradictions: Chart_11 and Lang_12.
Both flipped a real test in Experiment 9b, but showed claude_line as
"not covered" in the actual-line-coverage run. Since the statement at
claude_line is complete (not a truncated multi-line fragment like the other
3 cases), something else must be going on -- most likely the filename/class
matching in get_line_hits() is grabbing the wrong <class> element.

This script keeps the coverage.xml around (doesn't delete the checkout) and
prints every <class> entry found, plus hit counts for a window of lines
around claude_line, so we can see exactly what's happening.
"""

import xml.etree.ElementTree as ET
import subprocess
import os
import shutil

BUGS_TO_CHECK = [
    ("Chart", "11", "ShapeUtilities", 281),
    ("Lang", "12", "RandomStringUtils", 257),
]


def checkout_bug(project, bug_id, target_dir):
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir)
    result = subprocess.run(
        ['defects4j', 'checkout', '-p', project, '-v', f'{bug_id}b', '-w', target_dir],
        capture_output=True, text=True, timeout=120
    )
    return os.path.exists(target_dir)


def run_coverage(checkout_dir):
    result = subprocess.run(
        ['defects4j', 'coverage', '-w', checkout_dir],
        capture_output=True, text=True, timeout=600
    )
    print("  --- defects4j coverage stdout (last 20 lines) ---")
    for line in result.stdout.splitlines()[-20:]:
        print("   ", line)
    xml_path = os.path.join(checkout_dir, 'coverage.xml')
    return xml_path if os.path.exists(xml_path) else None


for project, bug_id, filename, claude_line in BUGS_TO_CHECK:
    print(f"\n{'='*60}")
    print(f"=== {project}_{bug_id}  (claude_line={claude_line}, filename hint='{filename}') ===")
    print(f"{'='*60}")

    tmp_dir = f"/tmp/{project}_{bug_id}_covdiag"
    print("Checking out...")
    if not checkout_bug(project, bug_id, tmp_dir):
        print("  Checkout failed")
        continue

    print("Running coverage...")
    xml_path = run_coverage(tmp_dir)
    if not xml_path:
        print("  Coverage XML not produced")
        continue

    tree = ET.parse(xml_path)
    root = tree.getroot()

    all_classes = root.findall('.//class')
    print(f"\nTotal <class> elements in coverage.xml: {len(all_classes)}")

    matching = [c for c in all_classes if filename in c.get('filename', '')]
    print(f"Classes whose filename contains '{filename}': {len(matching)}")
    for c in matching:
        print(f"  - filename={c.get('filename')!r}  name={c.get('name')!r}")

    if len(matching) > 1:
        print("\n  >>> MULTIPLE MATCHES FOUND -- this confirms the ambiguous-match theory <<<")

    print(f"\nLine-by-line hits near claude_line={claude_line} (+/- 5), across ALL matching class entries:")
    for c in matching:
        print(f"  --- class: {c.get('name')} ---")
        for line_el in c.findall('.//line'):
            n = int(line_el.get('number'))
            if abs(n - claude_line) <= 5:
                print(f"    line {n}: hits={line_el.get('hits')}")

    # keep the XML around for manual inspection instead of deleting the checkout
    saved_path = f"/tmp/{project}_{bug_id}_coverage_SAVED.xml"
    shutil.copy(xml_path, saved_path)
    print(f"\nCoverage XML saved to: {saved_path} (checkout left in place at {tmp_dir})")

print("\nDone.")

