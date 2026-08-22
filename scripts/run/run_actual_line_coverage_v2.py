"""
Experiment 9d v2: Actual-Line Coverage Check (content-matched line lookup)

Fix over the first version: apply_fix_to_file() finds and replaces a line by
matching its TEXT CONTENT, not by trusting claude_line as a line number. So
if Claude's self-reported line number is off by a line or two from where
that exact code actually lives, the fix still applies correctly (content
match doesn't care about line numbers) -- but querying coverage at the
reported claude_line can land on the wrong (often unrelated, 0-hit) line.

This version re-derives the REAL line number for each bug by searching the
checked-out file for original_code's exact text, and queries coverage at
that verified location instead of the raw reported number. Reports both, so
we can see how often they actually differ.

No new Claude calls needed -- reuses original_code from the existing CSVs.
"""

import xml.etree.ElementTree as ET
import subprocess
import os
import csv
import json
import shutil

BASE = os.path.expanduser("~/llm-bug-study/experiment")
BUGS_DIR = os.path.join(BASE, "data/bugs")
OUT_CSV = os.path.join(BASE, "results/java/results_actuallinecoverage_v2.csv")

SOURCES = [
    ("Chart", os.path.join(BASE, "results/java/results_v9_testfix.csv"), ["source", "src", "src/main/java", ""]),
    ("Lang", os.path.join(BASE, "results/java/results_v9_testfix_lang.csv"), ["src/main/java", "src", "source", ""]),
    ("Math", os.path.join(BASE, "results/java/results_v9_testfix_math.csv"), ["src/main/java", "src", "source", ""]),
]


def checkout_bug(project, bug_id, target_dir):
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir)
    result = subprocess.run(
        ['defects4j', 'checkout', '-p', project, '-v', f'{bug_id}b', '-w', target_dir],
        capture_output=True, text=True, timeout=120
    )
    return os.path.exists(target_dir)


def find_source_file(tmp_dir, file_path, src_candidates):
    for src in src_candidates:
        candidate = os.path.join(tmp_dir, src, file_path) if src else os.path.join(tmp_dir, file_path)
        if os.path.exists(candidate):
            return candidate
    return None


def find_real_line_number(full_file_path, target_text):
    """Search for the line whose stripped content exactly matches target_text."""
    if not target_text:
        return None
    with open(full_file_path) as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        if line.strip() == target_text.strip():
            return i + 1  # 1-indexed to match coverage.xml line numbers
    return None


def run_coverage(checkout_dir):
    subprocess.run(
        ['defects4j', 'coverage', '-w', checkout_dir],
        capture_output=True, text=True, timeout=600
    )
    xml_path = os.path.join(checkout_dir, 'coverage.xml')
    return xml_path if os.path.exists(xml_path) else None


def get_line_hits(xml_path, filename_contains, lineno):
    if not xml_path or not os.path.exists(xml_path) or lineno is None:
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


fields = [
    'project', 'bug_id', 'file',
    'actual_line', 'actual_hits', 'actual_covered',
    'claude_line_reported', 'claude_line_verified', 'line_number_differs',
    'claude_hits', 'claude_covered',
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

    for project, path, src_candidates in SOURCES:
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

            actual_line_raw = row.get('actual_line', '')
            claude_line_raw = row.get('claude_line', '')
            filename = row.get('file', '')
            original_code = row.get('original_code', '')

            if not actual_line_raw or not claude_line_raw or not original_code:
                print(f"  {project}_{bug_id}: missing data, skipping")
                continue

            actual_line = int(actual_line_raw)
            claude_line_reported = int(claude_line_raw)

            data_path = os.path.join(BUGS_DIR, f"{project}_{bug_id}", "data.json")
            if not os.path.exists(data_path):
                print(f"  {project}_{bug_id}: no data.json, skipping")
                continue
            with open(data_path) as f:
                data = json.load(f)
            file_path = data.get('file_path', '')
            if not filename:
                filename = os.path.basename(file_path).replace('.java', '')

            print(f"\n{project}_{bug_id} | actual={actual_line} claude_reported={claude_line_reported} file={filename}")

            tmp_dir = f"/tmp/{project}_{bug_id}_covv2"
            print("  Checking out...")
            if not checkout_bug(project, bug_id, tmp_dir):
                print("  Checkout failed, skipping")
                continue

            full_path = find_source_file(tmp_dir, file_path, src_candidates)
            claude_line_verified = None
            if full_path:
                claude_line_verified = find_real_line_number(full_path, original_code)
                if claude_line_verified is None:
                    print(f"  WARNING: could not find original_code text in file -- using reported line as fallback")
                    claude_line_verified = claude_line_reported
                elif claude_line_verified != claude_line_reported:
                    print(f"  Line number mismatch! reported={claude_line_reported}, actual location={claude_line_verified}")
            else:
                print(f"  Source file not found, using reported line as fallback")
                claude_line_verified = claude_line_reported

            print("  Running defects4j coverage...")
            xml_path = run_coverage(tmp_dir)
            if not xml_path:
                print("  Coverage failed, skipping")
                shutil.rmtree(tmp_dir, ignore_errors=True)
                continue

            actual_hits = get_line_hits(xml_path, filename, actual_line)
            claude_hits = get_line_hits(xml_path, filename, claude_line_verified)

            actual_covered = actual_hits is not None and actual_hits > 0
            claude_covered = claude_hits is not None and claude_hits > 0

            print(f"  actual  line {actual_line}: {actual_hits} hits | covered={actual_covered}")
            print(f"  claude  line {claude_line_verified} (verified, reported was {claude_line_reported}): "
                  f"{claude_hits} hits | covered={claude_covered}")

            writer.writerow({
                'project': project,
                'bug_id': bug_id,
                'file': filename,
                'actual_line': actual_line,
                'actual_hits': actual_hits,
                'actual_covered': actual_covered,
                'claude_line_reported': claude_line_reported,
                'claude_line_verified': claude_line_verified,
                'line_number_differs': claude_line_verified != claude_line_reported,
                'claude_hits': claude_hits,
                'claude_covered': claude_covered,
            })
            csvfile.flush()
            shutil.rmtree(tmp_dir, ignore_errors=True)

print(f"\nDone! Results saved to {OUT_CSV}")

