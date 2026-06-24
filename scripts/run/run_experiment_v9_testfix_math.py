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
RESULTS_MATH = os.path.expanduser("~/llm-bug-study/experiment/results/java/results_v5_math.csv")
OUT_CSV = os.path.expanduser("~/llm-bug-study/experiment/results/java/results_v9_testfix_math.csv")

HINT_MAP = {
    "off_by_one":    "a boundary or range handling error",
    "operator_swap": "an arithmetic expression error",
    "boolean_logic": "a conditional logic error",
    None:            "a logic error",
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
        except anthropic.RateLimitError:
            print(f"  Rate limit, waiting 90s...")
            time.sleep(90)
        except Exception as e:
            print(f"  Error: {e}")
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
    for i, line in enumerate(lines):
        if line.strip() == original_line.strip():
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
    fail_match = re.search(r'Failing tests: (\d+)', output)
    if fail_match:
        n_failing = int(fail_match.group(1))
    else:
        n_failing = len(re.findall(r'^\s+- ', output, re.MULTILINE))
    return n_failing == 0, n_failing, output[:300]

def checkout_bug(project, bug_id, target_dir):
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir)
    result = subprocess.run(
        ['defects4j', 'checkout', '-p', project, '-v', f'{bug_id}b', '-w', target_dir],
        capture_output=True, text=True, timeout=120
    )
    return os.path.exists(target_dir)

# load v5 Math results
bugs_to_fix = []
with open(RESULTS_MATH) as f:
    for row in csv.DictReader(f):
        if row['tier'] == '2' and row['reported_line']:
            bugs_to_fix.append(row)

print(f"Math bugs to process: {len(bugs_to_fix)}")

fields = [
    'bug_id', 'file', 'actual_line', 'claude_line',
    'original_code', 'fixed_code',
    'fix_applied', 'n_failing_before', 'n_failing_after',
    'tests_passed', 'improvement', 'claude_fix_response'
]

completed = set()
if os.path.exists(OUT_CSV):
    with open(OUT_CSV) as f:
        for row in csv.DictReader(f):
            completed.add(row['bug_id'])

with open(OUT_CSV, 'a', newline='') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=fields)
    if len(completed) == 0:
        writer.writeheader()

    for row in bugs_to_fix:
        bug_id = row['bug_id']
        if bug_id in completed:
            print(f"  Skipping Math_{bug_id}")
            continue

        actual_line = row.get('original_bug_line', '')
        claude_line = row['reported_line']
        hint = HINT_MAP.get(row.get('mutation_type'), 'a logic error')

        print(f"\nMath_{bug_id} | actual={actual_line} claude={claude_line}")

        data_path = os.path.join(BUGS_DIR, f"Math_{bug_id}", "data.json")
        if not os.path.exists(data_path):
            print(f"  No data.json, skipping")
            continue

        with open(data_path) as f:
            data = json.load(f)

        source_code = data.get('buggy_code', '')
        file_path = data.get('file_path', '')
        filename = file_path.split('/')[-1].replace('.java', '')

        tmp_dir = f"/tmp/Math_{bug_id}_fix"
        print(f"  Checking out...")
        if not checkout_bug('Math', bug_id, tmp_dir):
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
            # try multiple source paths
            full_path = None
            for src in ['src/main/java', 'src', 'source', '']:
                candidate = os.path.join(tmp_dir, src, file_path) if src else os.path.join(tmp_dir, file_path)
                if os.path.exists(candidate):
                    full_path = candidate
                    break

            if full_path:
                fix_applied = apply_fix_to_file(full_path, original_code, fixed_code)
                if fix_applied:
                    print(f"  Fix applied! Running tests...")
                    tests_passed, n_after, _ = run_tests(tmp_dir)
                    improvement = (n_before or 0) - (n_after or 0)
                    print(f"  Failing after: {n_after} | improvement: {improvement} | passed: {tests_passed}")
                else:
                    print(f"  Could not find original line in file")
            else:
                print(f"  Source file not found")

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
