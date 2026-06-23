import anthropic
import subprocess
import os
import csv
import json
import time
import shutil
import re

client = anthropic.Anthropic()

BUGS_DIR = os.path.expanduser("~/llm-bug-study/experiment/data/bugs")
RESULTS_V5 = os.path.expanduser("~/llm-bug-study/experiment/results/java/results_v5_chart.csv")
OUT_CSV = os.path.expanduser("~/llm-bug-study/experiment/results/java/results_v9_testfix.csv")

HINT_MAP = {
    "off_by_one":    "a boundary or range handling error",
    "operator_swap": "an arithmetic expression error",
    "boolean_logic": "a conditional logic error",
}

def ask_claude_for_fix(source_code, file_path, reported_line, hint):
    prompt = f"""You are analyzing a Java file from the Defects4J benchmark.
The bug is on line {reported_line} and is related to {hint}.

File: {file_path}
{source_code}

Provide a minimal one-line fix for the bug on line {reported_line}.
Respond in EXACTLY this format with no other text:
ORIGINAL: <the exact current content of line {reported_line}>
FIXED: <the corrected line>
EXPLANATION: <one sentence>"""

    for attempt in range(3):
        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text.strip()
        except Exception as e:
            if "rate" in str(e).lower():
                time.sleep(60)
            else:
                return None
    return None

def parse_fix(fix_response):
    original = None
    fixed = None
    for line in fix_response.splitlines():
        if line.startswith('ORIGINAL:'):
            original = line.replace('ORIGINAL:', '').strip()
        elif line.startswith('FIXED:'):
            fixed = line.replace('FIXED:', '').strip()
    return original, fixed

def apply_fix_to_file(full_file_path, original_line, fixed_line):
    with open(full_file_path) as f:
        lines = f.readlines()
    # try exact match first
    for i, line in enumerate(lines):
        if line.strip() == original_line.strip():
            # preserve original indentation
            indent = len(line) - len(line.lstrip())
            lines[i] = " " * indent + fixed_line.strip() + "\n"
            with open(full_file_path, "w") as f:
                f.writelines(lines)
            return True
    return False

def run_tests(checkout_dir):
    result = subprocess.run(
        ['defects4j', 'test', '-w', checkout_dir],
        capture_output=True, text=True, timeout=300
    )
    output = result.stdout + result.stderr
    # try "Failing tests: N" format
    fail_match = re.search(r'Failing tests: (\d+)', output)
    if fail_match:
        n_failing = int(fail_match.group(1))
    else:
        # count lines starting with "  - " which are failing test names
        n_failing = len(re.findall(r'^\s+- ', output, re.MULTILINE))
    passed = n_failing == 0
    return passed, n_failing, output[:300]

def checkout_bug(project, bug_id, target_dir, version='b'):
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir)
    result = subprocess.run(
        ['defects4j', 'checkout', '-p', project, '-v', f'{bug_id}{version}', '-w', target_dir],
        capture_output=True, text=True, timeout=120
    )
    return os.path.exists(target_dir)

# load v5 results - bugs where Claude reported a line
bugs_to_fix = []
with open(RESULTS_V5) as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['tier'] == '2' and row['reported_line']:
            bugs_to_fix.append(row)

print(f"Bugs to process: {len(bugs_to_fix)}")

fields = [
    'bug_id', 'file', 'actual_line', 'claude_line',
    'original_code', 'fixed_code',
    'fix_applied', 'n_failing_before', 'n_failing_after',
    'tests_passed', 'improvement',
    'claude_fix_response'
]

completed = set()
if os.path.exists(OUT_CSV):
    with open(OUT_CSV) as f:
        for row in csv.DictReader(f):
            completed.add(row['bug_id'])

print(f"Already completed: {len(completed)}")

with open(OUT_CSV, 'a', newline='') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=fields)
    if len(completed) == 0:
        writer.writeheader()

    for row in bugs_to_fix:
        bug_id = row['bug_id']
        if bug_id in completed:
            print(f"  Skipping Chart_{bug_id}")
            continue

        actual_line = row.get('original_bug_line', '')
        claude_line = row['reported_line']
        hint = HINT_MAP.get(row.get('mutation_type', ''), 'a logic error')

        print(f"\nChart_{bug_id} | actual={actual_line} claude={claude_line}")

        data_path = os.path.join(BUGS_DIR, f"Chart_{bug_id}", "data.json")
        if not os.path.exists(data_path):
            print(f"  No data.json, skipping")
            continue

        with open(data_path) as f:
            data = json.load(f)

        source_code = data.get('buggy_code', '')
        file_path = data.get('file_path', '')
        filename = file_path.split('/')[-1].replace('.java', '')

        # checkout buggy version to tmp
        tmp_dir = f"/tmp/Chart_{bug_id}_fix"
        print(f"  Checking out...")
        if not checkout_bug('Chart', bug_id, tmp_dir):
            print(f"  Checkout failed")
            continue

        # count failing tests BEFORE fix
        print(f"  Running tests before fix...")
        _, n_before, _ = run_tests(tmp_dir)
        print(f"  Failing before: {n_before}")

        # ask Claude for a fix
        print(f"  Asking Claude for fix at line {claude_line}...")
        fix_response = ask_claude_for_fix(source_code, file_path, claude_line, hint)
        if not fix_response:
            print(f"  Claude returned nothing")
            shutil.rmtree(tmp_dir, ignore_errors=True)
            continue

        original_code, fixed_code = parse_fix(fix_response)
        print(f"  ORIGINAL: {original_code}")
        print(f"  FIXED:    {fixed_code}")

        fix_applied = False
        n_after = None
        tests_passed = False
        improvement = None

        if original_code and fixed_code:
            # find the actual file in checkout
            full_path = os.path.join(tmp_dir, 'source', file_path)
            if not os.path.exists(full_path):
                # try alternate source paths
                for src_dir in ['src', 'source', 'src/main/java']:
                    alt = os.path.join(tmp_dir, src_dir, file_path)
                    if os.path.exists(alt):
                        full_path = alt
                        break

            if os.path.exists(full_path):
                fix_applied = apply_fix_to_file(full_path, original_code, fixed_code)
                if fix_applied:
                    print(f"  Fix applied! Running tests...")
                    tests_passed, n_after, _ = run_tests(tmp_dir)
                    improvement = (n_before or 0) - (n_after or 0)
                    print(f"  Failing after: {n_after} | improvement: {improvement} | passed: {tests_passed}")
                else:
                    print(f"  Could not find original line in file")
            else:
                print(f"  File not found: {full_path}")

        writer.writerow({
            'bug_id': bug_id,
            'file': filename,
            'actual_line': actual_line,
            'claude_line': claude_line,
            'original_code': original_code or '',
            'fixed_code': fixed_code or '',
            'fix_applied': fix_applied,
            'n_failing_before': n_before,
            'n_failing_after': n_after,
            'tests_passed': tests_passed,
            'improvement': improvement,
            'claude_fix_response': (fix_response or '').replace('\n', ' ')
        })
        csvfile.flush()
        shutil.rmtree(tmp_dir, ignore_errors=True)
        time.sleep(5)

print(f"\nDone! Results saved to {OUT_CSV}")

def run_lang_testfix():
    """Run test fix experiment on Lang bugs using v5_lang results"""
    import json, shutil

    RESULTS_LANG = os.path.expanduser("~/llm-bug-study/experiment/results/java/results_v5_lang.csv")
    OUT_LANG = os.path.expanduser("~/llm-bug-study/experiment/results/java/results_v9_testfix_lang.csv")

    bugs_to_fix = []
    with open(RESULTS_LANG) as f:
        for row in csv.DictReader(f):
            if row['tier'] == '2' and row['reported_line']:
                bugs_to_fix.append(row)

    print(f"\nLang bugs to process: {len(bugs_to_fix)}")

    fields = [
        'bug_id', 'file', 'actual_line', 'claude_line',
        'original_code', 'fixed_code',
        'fix_applied', 'n_failing_before', 'n_failing_after',
        'tests_passed', 'improvement', 'claude_fix_response'
    ]

    completed = set()
    if os.path.exists(OUT_LANG):
        with open(OUT_LANG) as f:
            for row in csv.DictReader(f):
                completed.add(row['bug_id'])

    with open(OUT_LANG, 'a', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fields)
        if len(completed) == 0:
            writer.writeheader()

        for row in bugs_to_fix:
            bug_id = row['bug_id']
            if bug_id in completed:
                print(f"  Skipping Lang_{bug_id}")
                continue

            actual_line = row.get('original_bug_line', '')
            claude_line = row['reported_line']
            hint = HINT_MAP.get(row.get('mutation_type', ''), 'a logic error')

            print(f"\nLang_{bug_id} | actual={actual_line} claude={claude_line}")

            data_path = os.path.join(BUGS_DIR, f"Lang_{bug_id}", "data.json")
            if not os.path.exists(data_path):
                print(f"  No data.json, skipping")
                continue

            with open(data_path) as f:
                data = json.load(f)

            source_code = data.get('buggy_code', '')
            file_path = data.get('file_path', '')
            filename = file_path.split('/')[-1].replace('.java', '')

            tmp_dir = f"/tmp/Lang_{bug_id}_fix"
            print(f"  Checking out...")
            if not checkout_bug('Lang', bug_id, tmp_dir):
                print(f"  Checkout failed")
                continue

            print(f"  Running tests before fix...")
            _, n_before, _ = run_tests(tmp_dir)
            print(f"  Failing before: {n_before}")

            print(f"  Asking Claude for fix at line {claude_line}...")
            fix_response = ask_claude_for_fix(source_code, file_path, claude_line, hint)
            if not fix_response:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                continue

            original_code, fixed_code = parse_fix(fix_response)
            print(f"  ORIGINAL: {original_code}")
            print(f"  FIXED:    {fixed_code}")

            fix_applied = False
            n_after = None
            tests_passed = False
            improvement = None

            if original_code and fixed_code:
                full_path = os.path.join(tmp_dir, 'src', 'main', 'java', file_path)
                if not os.path.exists(full_path):
                    for src in ['src', 'source', 'src/main/java', '']:
                        alt = os.path.join(tmp_dir, src, file_path) if src else os.path.join(tmp_dir, file_path)
                        if os.path.exists(alt):
                            full_path = alt
                            break

                if os.path.exists(full_path):
                    fix_applied = apply_fix_to_file(full_path, original_code, fixed_code)
                    if fix_applied:
                        print(f"  Fix applied! Running tests...")
                        tests_passed, n_after, _ = run_tests(tmp_dir)
                        improvement = (n_before or 0) - (n_after or 0)
                        print(f"  Failing after: {n_after} | improvement: {improvement} | passed: {tests_passed}")
                    else:
                        print(f"  Could not find original line in file")
                else:
                    print(f"  File not found: {full_path}")

            writer.writerow({
                'bug_id': bug_id,
                'file': filename,
                'actual_line': actual_line,
                'claude_line': claude_line,
                'original_code': original_code or '',
                'fixed_code': fixed_code or '',
                'fix_applied': fix_applied,
                'n_failing_before': n_before,
                'n_failing_after': n_after,
                'tests_passed': tests_passed,
                'improvement': improvement,
                'claude_fix_response': (fix_response or '').replace('\n', ' ')
            })
            csvfile.flush()
            shutil.rmtree(tmp_dir, ignore_errors=True)
            time.sleep(5)

    print(f"\nDone! Results saved to {OUT_LANG}")

if __name__ == "__main__":
    run_lang_testfix()
