"""
Experiment 9d: Actual-Line Coverage Check

Question (from Prof. Gulzar): do the tests actually touch/execute the
documented bug line at all?

This extends Experiment 8's JaCoCo coverage methodology to ALL 50 bugs used
in Experiment 9/9b/9c. Experiment 8's original run only covered 21/21 Chart
bugs and 5/12 Lang bugs, and never ran Math at all -- this fills that gap,
using actual_line/claude_line pulled directly from the (already-verified)
results_v9_testfix*.csv rather than the older tier2 source Experiment 8
used for Chart.

No Claude calls needed -- this is pure test-suite instrumentation.
"""

import xml.etree.ElementTree as ET
import subprocess
import os
import csv
import json
import shutil

BASE = os.path.expanduser("~/llm-bug-study/experiment")
BUGS_DIR = os.path.join(BASE, "data/bugs")
OUT_CSV = os.path.join(BASE, "results/java/results_actuallinecoverage.csv")

SOURCES = [
    ("Chart", os.path.join(BASE, "results/java/results_v9_testfix.csv")),
    ("Lang", os.path.join(BASE, "results/java/results_v9_testfix_lang.csv")),
    ("Math", os.path.join(BASE, "results/java/results_v9_testfix_math.csv")),
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
    subprocess.run(
        ['defects4j', 'coverage', '-w', checkout_dir],
        capture_output=True, text=True, timeout=600
    )
    xml_path = os.path.join(checkout_dir, 'coverage.xml')
    return xml_path if os.path.exists(xml_path) else None


def get_line_hits(xml_path, filename_contains, lineno):
    if not xml_path or not os.path.exists(xml_path):
        return None
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        for cls in root.findall('.//class'):
            if filename_contains in cls.get('filename', ''):
                for line in cls.findall('.//line'):
                    if int(line.get('number')) == lineno:
                        return int(line.get('hits', 0))
        return None
    except Exception as e:
        print(f"  XML error: {e}")
        return None


def get_file_coverage(xml_path, filename_contains):
    if not xml_path or not os.path.exists(xml_path):
        return None, None, None
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        for cls in root.findall('.//class'):
            if filename_contains in cls.get('filename', ''):
                lines = cls.findall('.//line')
                total = len(lines)
                covered = sum(1 for l in lines if int(l.get('hits', 0)) > 0)
                pct = round(100 * covered / total, 1) if total > 0 else 0
                return covered, total, pct
        return None, None, None
    except Exception:
        return None, None, None


fields = [
    'project', 'bug_id', 'file', 'actual_line', 'claude_line',
    'actual_hits', 'claude_hits',
    'actual_covered', 'claude_covered',
    'file_coverage_pct',
]

completed = set()
if os.path.exists(OUT_CSV):
    with open(OUT_CSV) as f:
        for row in csv.DictReader(f):
            completed.add((row['project'], row['bug_id']))

print(f"Already completed: {len(completed)}")

with open(OUT_CSV, 'a', newline='') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=fields)
    if len(completed) == 0:
        writer.writeheader()

    for project, path in SOURCES:
        if not os.path.exists(path):
            print(f"Skipping {project}: {path} not found")
            continue
        with open(path) as f:
            rows = list(csv.DictReader(f))

        print(f"\n=== {project}: {len(rows)} bugs ===")

        for row in rows:
            bug_id = row['bug_id']
            if (project, bug_id) in completed:
                print(f"  Skipping {project}_{bug_id} (already done)")
                continue

            actual_line = row.get('actual_line', '')
            claude_line = row.get('claude_line', '')
            filename = row.get('file', '')

            if not actual_line or not claude_line:
                print(f"  {project}_{bug_id}: missing line info, skipping")
                continue

            actual_line = int(actual_line)
            claude_line = int(claude_line)

            data_path = os.path.join(BUGS_DIR, f"{project}_{bug_id}", "data.json")
            if os.path.exists(data_path):
                with open(data_path) as f:
                    data = json.load(f)
                # prefer the classname derivable from file_path if filename column is empty/odd
                if not filename:
                    filename = os.path.basename(data.get('file_path', '')).replace('.java', '')

            print(f"\n{project}_{bug_id} | actual={actual_line} claude={claude_line} file={filename}")

            tmp_dir = f"/tmp/{project}_{bug_id}_cov"
            print("  Checking out...")
            if not checkout_bug(project, bug_id, tmp_dir):
                print("  Checkout failed, skipping")
                continue

            print("  Running defects4j coverage (this runs the full test suite, can take a while)...")
            xml_path = run_coverage(tmp_dir)
            if not xml_path:
                print("  Coverage failed, skipping")
                shutil.rmtree(tmp_dir, ignore_errors=True)
                continue

            actual_hits = get_line_hits(xml_path, filename, actual_line)
            claude_hits = get_line_hits(xml_path, filename, claude_line)
            file_cov, file_total, file_pct = get_file_coverage(xml_path, filename)

            actual_covered = actual_hits is not None and actual_hits > 0
            claude_covered = claude_hits is not None and claude_hits > 0

            print(f"  actual line {actual_line}: {actual_hits} hits | covered={actual_covered}")
            print(f"  claude line {claude_line}: {claude_hits} hits | covered={claude_covered}")
            print(f"  file coverage: {file_pct}% ({file_cov}/{file_total} lines)")

            writer.writerow({
                'project': project,
                'bug_id': bug_id,
                'file': filename,
                'actual_line': actual_line,
                'claude_line': claude_line,
                'actual_hits': actual_hits,
                'claude_hits': claude_hits,
                'actual_covered': actual_covered,
                'claude_covered': claude_covered,
                'file_coverage_pct': file_pct,
            })
            csvfile.flush()
            shutil.rmtree(tmp_dir, ignore_errors=True)

print(f"\nDone! Results saved to {OUT_CSV}")

