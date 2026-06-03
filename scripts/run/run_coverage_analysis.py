import xml.etree.ElementTree as ET
import subprocess
import os
import csv
import time

BUGS_DIR = os.path.expanduser("~/llm-bug-study/experiment/data/bugs")
RESULTS_V5 = os.path.expanduser("~/llm-bug-study/experiment/results/java/results_v5_chart.csv")
OUT_CSV = os.path.expanduser("~/llm-bug-study/experiment/results/java/results_coverage.csv")

def run_coverage(checkout_dir):
    result = subprocess.run(
        ['defects4j', 'coverage', '-w', checkout_dir],
        capture_output=True, text=True
    )
    xml_path = os.path.join(checkout_dir, 'coverage.xml')
    if os.path.exists(xml_path):
        return xml_path
    return None

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
    except:
        return None, None, None

def get_line_rank(xml_path, filename_contains, lineno):
    """What percentile is this line's hit count among all lines in the file?"""
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

claude_lines = {}
with open(RESULTS_V5) as f:
    reader = csv.DictReader(f)
    for row in reader:
        bug_id = row['bug_id']
        if row['tier'] == '2':
            claude_lines[bug_id] = {
                'reported': int(row['reported_line']) if row['reported_line'] else None,
                'actual': int(row['original_bug_line']) if row['original_bug_line'] else None,
                'file': row['file'].replace('.java', '')
            }

fields = [
    'bug_id', 'file', 'actual_line', 'claude_line',
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

with open(OUT_CSV, 'a', newline='') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=fields)
    if len(completed) == 0:
        writer.writeheader()

    for bug_id, info in sorted(claude_lines.items(), key=lambda x: int(x[0])):
        if bug_id in completed:
            print(f"Skipping Chart_{bug_id}")
            continue

        actual_line = info['actual']
        claude_line = info['reported']
        filename = info['file']

        if not actual_line or not claude_line:
            print(f"Chart_{bug_id}: missing line info, skipping")
            continue

        print(f"\nChart_{bug_id} | actual={actual_line} claude={claude_line} file={filename}")

        checkout_dir = os.path.join(BUGS_DIR, f"Chart_{bug_id}", "buggy")
        if not os.path.exists(checkout_dir):
            print(f"  No buggy checkout, skipping")
            continue

        xml_path = run_coverage(checkout_dir)
        if not xml_path:
            print(f"  Coverage failed")
            continue

        actual_hits = get_line_hits(xml_path, filename, actual_line)
        claude_hits = get_line_hits(xml_path, filename, claude_line)
        file_cov, file_total, file_pct = get_file_coverage(xml_path, filename)
        actual_rank = get_line_rank(xml_path, filename, actual_line)
        claude_rank = get_line_rank(xml_path, filename, claude_line)

        actual_covered = actual_hits is not None and actual_hits > 0
        claude_covered = claude_hits is not None and claude_hits > 0

        print(f"  actual  line {actual_line}: {actual_hits} hits | covered={actual_covered} | rank={actual_rank}%ile")
        print(f"  claude  line {claude_line}: {claude_hits} hits | covered={claude_covered} | rank={claude_rank}%ile")
        print(f"  file coverage: {file_pct}% ({file_cov}/{file_total} lines)")

        writer.writerow({
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
        time.sleep(2)

print(f"\nDone! Results saved to {OUT_CSV}")
