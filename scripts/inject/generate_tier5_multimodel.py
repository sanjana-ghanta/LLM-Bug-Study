"""
Generates a Tier 5 semantic rewrite PER MODEL, instead of one shared
rewrite generated only by Claude. Stores results under a new field,
tier5_code_by_model (a dict keyed by model_key), so it doesn't clobber
any existing single-model tier5_code field.

Usage:
    python3 generate_tier5_multimodel.py --model claude
    python3 generate_tier5_multimodel.py --model glm-5.3-thinking
    python3 generate_tier5_multimodel.py --model deepseek-v4-flash-thinking
    python3 generate_tier5_multimodel.py --model gpt-oss-thinking

Run once per model you want a rewrite from. Resumable -- skips any bug that
already has this model's rewrite stored.
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from lib.llm_clients import call_llm

BUGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "bugs")

MAX_TOKENS = 4096
BETWEEN_CALL_SLEEP_SECONDS = 8
RETRY_WAIT_SECONDS = 30


def generate_semantic_rewrite(model_key, buggy_code, file_path):
    prompt = f"""You are a Java code transformation tool.
Rewrite the following Java code so that:
1. The code looks different on the surface (rename variables, restructure expressions, change loop styles)
2. The semantic behavior is IDENTICAL - including any bugs present
3. Do not fix any bugs - preserve them exactly
4. Return ONLY the rewritten code with no explanation

File: {file_path}

Code:
{buggy_code}"""

    try:
        result = call_llm(
            model_key,
            system_prompt="You are a precise code transformation tool. Follow instructions exactly.",
            user_prompt=prompt,
            max_tokens=MAX_TOKENS,
        )
    except Exception as e:
        err_str = str(e).lower()
        if "rate limit" in err_str or "429" in err_str:
            print(f"  Rate limit, waiting {RETRY_WAIT_SECONDS}s...")
            time.sleep(RETRY_WAIT_SECONDS)
            try:
                result = call_llm(
                    model_key,
                    system_prompt="You are a precise code transformation tool. Follow instructions exactly.",
                    user_prompt=prompt,
                    max_tokens=MAX_TOKENS,
                )
            except Exception as e2:
                print(f"  ERROR (retry failed): {e2}")
                return None
        else:
            print(f"  ERROR: {e}")
            return None

    if not result:
        print(f"  WARNING: empty response (thinking model may need a higher MAX_TOKENS)")
        return None

    result = result.strip()
    if result.startswith("```"):
        result = "\n".join(result.split("\n")[1:])
    if result.endswith("```"):
        result = "\n".join(result.split("\n")[:-1])
    return result.strip()


def process_bug(model_key, data_json_path):
    with open(data_json_path) as f:
        data = json.load(f)

    by_model = data.get("tier5_code_by_model", {})
    if by_model.get(model_key):
        print(f"  Skipping {data['project']}-{data['bug_id']}, tier5 for {model_key} already done")
        return

    print(f"  Generating tier5 ({model_key}) for {data['project']}-{data['bug_id']}...")
    tier5_code = generate_semantic_rewrite(model_key, data["buggy_code"], data["file_path"])
    if tier5_code is None:
        return

    by_model[model_key] = tier5_code
    data["tier5_code_by_model"] = by_model
    with open(data_json_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Saved.")
    time.sleep(BETWEEN_CALL_SLEEP_SECONDS)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="Model key from lib.config.MODELS")
    args = parser.parse_args()

    for bug_dir in sorted(os.listdir(BUGS_DIR)):
        data_path = os.path.join(BUGS_DIR, bug_dir, "data.json")
        if os.path.exists(data_path):
            process_bug(args.model, data_path)

    print(f"All tier5 rewrites done for model={args.model}!")


if __name__ == "__main__":
    main()

