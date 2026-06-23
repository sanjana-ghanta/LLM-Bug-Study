import xml.etree.ElementTree as ET
import subprocess
import os
import csv
import json
import time

BUGS_DIR = os.path.expanduser("~/llm-bug-study/experiment/data/bugs")
RESULTS_V3 = os.path.expanduser("~/llm-bug-study/experiment/results/java/results_v3_lang.csv")
OUT_CSV = os.path.expanduser("~/llm-bug-study/experiment/results/java/results_coverage_lang.csv")

def run_coverage(checkout_dir):
    xml_path = os.path.join(checkout_dir, 'coverage.xml')
    if os.path.exists(xml_path):
        print(f"  Using cached coverage.xml")
        return xml_path
    result = subprocess.run(
        ['defects4j', 'coverage', '-w', checkout_dir],
        capture_output=True, text=True, timeout=300
    )
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

def get_line_rank(xml_path, filename_contains, lineno):
    if not xml_path or not os.path.exists(xml_path):
        return None
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        for cls in root.findall('.//class'):
            if filename_contains in cls.get('filename', ''):
                all_hits = []
                target_hits = None
                for line in cls.findall('.//line'):
                    h = int(line.get('hits', 0))
                    all_hits.append(h)
                    if int(line.get('number')) == lineno:
                        target_hits = h
                if target_hits is None or not all_hits:
                    return None
                rank = sum(1 for h in all_hits if h <= target_hits) / len(all_hits)
                return round(rank * 100, 1)
        return None
    except:
        return None

def get_file_coverage_pct(xml_path, filename_contains):
    if not xml_path or not os.path.exists(xml_path):
        return None
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        for cls in root.findall('.//class'):
            if filename_contains in cls.get('filename', ''):
                lines = cls.findall('.//line')
                total = len(lines)
                covered = sum(1 for l in lines if int(l.get('hits', 0)) > 0)
                return round(100 * covered / total, 1) if total > 0 else 0
        return None
    except:
        return None

# load v3 results - only tier 2 with both lines
claude_lines = {}
with open(RESULTS_V3) as f:
    reader = csv.DictReader(f)
    for row in reader:
        bug_id = row['bug_id']
        if row['tier'] != '2':
            continue
        reported = int(row['reported_line']) if row.get('reported_line') else None
        actual = int(row['original_bug_line']) if row.get('original_bug_line') else None
        if not reported or not actual:
            continue
        # get filename from data.json
        data_path = os.path.join(BUGS_DIR, f"Lang_{bug_id}", "data.json")
        if not os.path.exists(data_path):
            continue
        with open(data_path) as f:
            data = json.load(f)
        file_path = data.get('file_path', '')
        filename = file_path.split('/')[-1].replace('.java', '')
        claude_lines[bug_id] = {
            'reported': reported,
            'actual': actual,
            'file': filename
        }

print(f"Bugs with both lines: {len(claude_lines)}")

fields = [
    'project', 'bug_id', 'file',
    'actual_line', 'claude_line',
    'actual_hits', 'claude_hits',
    'actual_covered', 'claude_covered',
    'actual_rank_pct', 'claude_rank_pct',
    'file_coverage_pct'
]

completed = set()
if os.path.exists(OUT_CSV):
    with open(OUT_CSV) as f:
        reader = csv.DictReader(f)
        for row in reader:
            completed.add(row['bug_id'])

print(f"Already completed: {len(completed)}")

with open(OUT_CSV, 'a', newline='') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=fields)
    if len(completed) == 0:
        writer.writeheader()

    for bug_id, info in sorted(claude_lines.items(), key=lambda x: int(x[0])):
        if bug_id in completed:
            print(f"  Skipping Lang_{bug_id}")
            continue

        actual_line = info['actual']
        claude_line = info['reported']
        filename = info['file']

        print(f"\nLang_{bug_id} | actual={actual_line} claude={claude_line} file={filename}")

        checkout_dir = os.path.join(BUGS_DIR, f"Lang_{bug_id}", "buggy")
        if not os.path.exists(checkout_dir):
            print(f"  No buggy checkout, skipping")
            continue

        xml_path = run_coverage(checkout_dir)
        if not xml_path:
            print(f"  Coverage failed")
            continue

        actual_hits = get_line_hits(xml_path, filename, actual_line)
        claude_hits = get_line_hits(xml_path, filename, claude_line)
        actual_rank = get_line_rank(xml_path, filename, actual_line)
        claude_rank = get_line_rank(xml_path, filename, claude_line)
        file_pct = get_file_coverage_pct(xml_path, filename)

        actual_covered = actual_hits is not None and actual_hits > 0
        claude_covered = claude_hits is not None and claude_hits > 0

        print(f"  actual  line {actual_line}: {actual_hits} hits | covered={actual_covered} | rank={actual_rank}%ile")
        print(f"  claude  line {claude_line}: {claude_hits} hits | covered={claude_covered} | rank={claude_rank}%ile")
        print(f"  file coverage: {file_pct}%")

        writer.writerow({
            'project': 'Lang',
            'bug_id': bug_id,
            'file': filename,
            'actual_line': actual_line,
            'claude_line': claude_line,
            'actual_hits': actual_hits,
            'claude_hits': claude_hits,
            'actual_covered': actual_covered,
            'claude_covered': claude_covered,
            'actual_rank_pct': actual_rank,
            'claude_rank_pct': claude_rank,
            'file_coverage_pct': file_pct
        })
        csvfile.flush()
        time.sleep(1)

print(f"\nDone! Results saved to {OUT_CSV}")
