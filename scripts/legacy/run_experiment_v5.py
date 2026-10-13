import re
import json
import os
import csv
import time
from openai import OpenAI

client = OpenAI(
    api_key=os.environ.get("VT_API_KEY", "PASTE_YOUR_KEY_HERE"),
    base_url="https://llm-api.arc.vt.edu/api/v1",
)

MODEL = "gpt-oss-120b"

BENCHMARK_NAME = {
    "Lang":  "Defects4J",
    "Math":  "Defects4J",
    "Chart": "Defects4J",
}

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

def ask_llm(project, bug_id, file_path, hint, benchmark, source_code, manifest):
    manifest_str = "\n".join(manifest[:200])
    if len(manifest) > 200:
        manifest_str += f"\n... and {len(manifest) - 200} more files"

    prompt = f"""You are analyzing code from the {benchmark} benchmark.

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
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful code analysis assistant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=512
            )
            text = response.choices[0].message.content
            if not text:
                print(f"  Empty response (attempt {attempt+1})")
                time.sleep(10)
                continue

            text = text.strip()
            line_no = None
            for line in text.splitlines():
                if line.startswith("LINE:"):
                    val = line.replace("LINE:", "").strip()
                    match = re.match(r'\d+', val)
                    if match:
                        line_no = int(match.group(0))

            return line_no, text

        except Exception as e:
            if "rate" in str(e).lower():
                wait = 60 * (attempt + 1)
                print(f"  Rate limit, waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"  Error: {e}")
                time.sleep(10)

    return None, "max retries exceeded"

def classify(reported_line, original_bug_line, tier, tolerance=5):
    if tier == 1:
        if reported_line is None:
            return "reasoned_no_bug"
        else:
            return "pattern_matched_clean"
    else:
        if reported_line is None:
            return "none"
        if original_bug_line and abs(reported_line - int(original_bug_line)) <= tolerance:
            return "correct"
        return "wrong"

def load_completed(csv_path):
    completed = set()
    if os.path.exists(csv_path):
        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                completed.add((row["project"], row["bug_id"], row["tier"]))
    return completed

if __name__ == "__main__":
    BUGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../data/bugs")
    OUT_CSV  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../results/java/results_v5_gptoss_chart.csv")

    fields = [
        "project", "bug_id", "tier", "file", "hint", "mutation_type",
        "reported_line", "original_bug_line", "result", "response"
    ]

    completed = load_completed(OUT_CSV)
    print(f"Already completed: {len(completed)}")

    all_chart = sorted(
        [d for d in os.listdir(BUGS_DIR) if d.startswith("Chart")],
        key=lambda x: int(x.split("_")[1]),
        reverse=True
    )
    print(f"Running on {len(all_chart)} Chart bugs (tiers 1 & 2) in reverse order")
    print(f"Model: {MODEL}")

    with open(OUT_CSV, "a", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fields)
        if len(completed) == 0:
            writer.writeheader()

        for bug_dir in all_chart:
            data_path = os.path.join(BUGS_DIR, bug_dir, "data.json")
            if not os.path.exists(data_path):
                continue

            with open(data_path) as f:
                data = json.load(f)

            project   = data["project"]
            bug_id    = str(data["bug_id"])
            benchmark = BENCHMARK_NAME.get(project, "Defects4J")
            hint      = HINT_MAP.get(data.get("tier3_mutation_type"), HINT_MAP[None])
            file_path = data["file_path"]
            orig_line = data.get("original_bug_line")
            bug_dir_path = os.path.dirname(data_path)

            tiers = {
                1: ("patched_code", "patched"),
                2: ("buggy_code",   "buggy"),
            }

            for tier_num, (code_key, checkout_dir) in tiers.items():
                if (project, bug_id, str(tier_num)) in completed:
                    print(f"  Skipping tier {tier_num} for {project}-{bug_id}")
                    continue

                source_code = data.get(code_key, "")
                if not source_code:
                    print(f"  No code for tier {tier_num}, skipping")
                    continue

                project_dir = os.path.join(bug_dir_path, checkout_dir)
                manifest = get_file_manifest(project_dir) if os.path.exists(project_dir) else []

                print(f"\nProcessing {bug_dir} tier {tier_num} | hint: {hint} | {len(manifest)} files")

                reported_line, response_text = ask_llm(
                    project, bug_id, file_path,
                    hint, benchmark, source_code, manifest
                )

                result = classify(reported_line, orig_line, tier_num)
                print(f"  reported={reported_line} actual={orig_line} → {result}")

                writer.writerow({
                    "project":           project,
                    "bug_id":            bug_id,
                    "tier":              tier_num,
                    "file":              file_path.split("/")[-1],
                    "hint":              hint,
                    "mutation_type":     data.get("tier3_mutation_type"),
                    "reported_line":     reported_line,
                    "original_bug_line": orig_line,
                    "result":            result,
                    "response":          response_text.replace("\n", " ") if response_text else ""
                })
                csvfile.flush()
                time.sleep(5)

    print(f"\nDone! Results saved to {OUT_CSV}")
