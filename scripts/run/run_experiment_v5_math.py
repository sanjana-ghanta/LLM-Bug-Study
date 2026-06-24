import re
import json
import os
import csv
import time
import anthropic

client = anthropic.Anthropic()

BUGS_DIR = os.path.expanduser("~/llm-bug-study/experiment/data/bugs")
OUT_CSV = os.path.expanduser("~/llm-bug-study/experiment/results/java/results_v5_math.csv")

HINT_MAP = {
    "off_by_one":    "a boundary or range handling error",
    "operator_swap": "an arithmetic expression error",
    "boolean_logic": "a conditional logic error",
    None:            "a logic error",
}

def get_file_manifest(project_dir):
    manifest = []
    for root, dirs, files in os.walk(project_dir):
        dirs[:] = [d for d in dirs if not d.startswith('.')
                   and d not in ('build', 'target', '.svn', '.git')]
        for f in files:
            if f.endswith('.java'):
                rel_path = os.path.relpath(os.path.join(root, f), project_dir)
                manifest.append(rel_path)
    return sorted(manifest)

def ask_llm(project, bug_id, file_path, hint, source_code, manifest):
    manifest_str = "\n".join(manifest[:200])
    if len(manifest) > 200:
        manifest_str += f"\n... and {len(manifest) - 200} more files"

    prompt = f"""You are analyzing code from the Defects4J benchmark.

This is bug ID {bug_id} from the {project} project in the Defects4J buggy dataset.
This bug is known to be related to {hint}.

Here is the full project file structure:
{manifest_str}

Here is the source file:
{file_path}
{source_code}

What line is the bug on?

Please respond in this exact format:
LINE: <line number>
REASON: <one sentence explanation of what specifically is wrong>"""

    for attempt in range(3):
        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}]
            )
            text = response.content[0].text.strip()
            line_no = None
            for line in text.splitlines():
                if line.startswith("LINE:"):
                    val = line.replace("LINE:", "").strip()
                    match = re.match(r'\d+', val)
                    if match:
                        line_no = int(match.group(0))
            return line_no, text
        except anthropic.RateLimitError:
            wait = 90 * (attempt + 1)
            print(f"  Rate limit, waiting {wait}s...")
            time.sleep(wait)
        except Exception as e:
            print(f"  Error: {e}")
            time.sleep(10)
    return None, "max retries exceeded"

def classify(reported_line, original_bug_line, tolerance=5):
    if reported_line is None:
        return "none"
    if original_bug_line and abs(reported_line - int(original_bug_line)) <= tolerance:
        return "correct"
    return "wrong"

def load_completed(csv_path):
    completed = set()
    if os.path.exists(csv_path):
        with open(csv_path, newline="") as f:
            for row in csv.DictReader(f):
                completed.add((row["project"], row["bug_id"], row["tier"]))
    return completed

if __name__ == "__main__":
    all_math = sorted(
        [d for d in os.listdir(BUGS_DIR) if d.startswith("Math_")],
        key=lambda x: int(x.split("_")[1])
    )
    print(f"Found {len(all_math)} Math bugs")

    fields = [
        "project", "bug_id", "tier", "file", "hint", "mutation_type",
        "reported_line", "original_bug_line", "result", "response"
    ]

    completed = load_completed(OUT_CSV)
    print(f"Already completed: {len(completed)}")

    with open(OUT_CSV, "a", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fields)
        if len(completed) == 0:
            writer.writeheader()

        for bug_dir in all_math:
            data_path = os.path.join(BUGS_DIR, bug_dir, "data.json")
            if not os.path.exists(data_path):
                continue

            with open(data_path) as f:
                data = json.load(f)

            project = data["project"]
            bug_id = str(data["bug_id"])
            file_path = data["file_path"]
            orig_line = data.get("original_bug_line")
            hint = HINT_MAP.get(data.get("tier3_mutation_type"), HINT_MAP[None])
            filename = file_path.split("/")[-1]

            tiers = {
                1: ("patched_code", "patched"),
                2: ("buggy_code", "buggy"),
            }

            for tier_num, (code_key, checkout_dir) in tiers.items():
                if (project, bug_id, str(tier_num)) in completed:
                    print(f"  Skipping tier {tier_num} for {project}-{bug_id}")
                    continue

                source_code = data.get(code_key, "")
                if not source_code:
                    print(f"  No code for tier {tier_num}, skipping")
                    continue

                bug_dir_path = os.path.join(BUGS_DIR, bug_dir)
                project_dir = os.path.join(bug_dir_path, checkout_dir)
                manifest = get_file_manifest(project_dir) if os.path.exists(project_dir) else []

                print(f"\n{bug_dir} tier {tier_num} | hint: {hint} | {len(manifest)} files")

                reported_line, response_text = ask_llm(
                    project, bug_id, file_path, hint, source_code, manifest
                )

                result = classify(reported_line, orig_line)
                print(f"  reported={reported_line} actual={orig_line} → {result}")

                writer.writerow({
                    "project": project,
                    "bug_id": bug_id,
                    "tier": tier_num,
                    "file": filename,
                    "hint": hint,
                    "mutation_type": data.get("tier3_mutation_type"),
                    "reported_line": reported_line,
                    "original_bug_line": orig_line,
                    "result": result,
                    "response": response_text.replace("\n", " ") if response_text else ""
                })
                csvfile.flush()
                time.sleep(5)

    print(f"\nDone! Results saved to {OUT_CSV}")
