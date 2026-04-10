import json
import os
import time
import anthropic

client = anthropic.Anthropic()

def generate_semantic_rewrite(buggy_code, file_path):
    prompt = f"""You are a Java code transformation tool. 
Rewrite the following Java code so that:
1. The code looks different on the surface (rename variables, restructure expressions, change loop styles)
2. The semantic behavior is IDENTICAL - including any bugs present
3. Do not fix any bugs - preserve them exactly
4. Return ONLY the rewritten code with no explanation

File: {file_path}

Code:
{buggy_code}"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    )
    
    result = response.content[0].text.strip()
    if result.startswith("```"):
        result = "\n".join(result.split("\n")[1:])
    if result.endswith("```"):
        result = "\n".join(result.split("\n")[:-1])
    return result.strip()

def process_bug(data_json_path):
    with open(data_json_path) as f:
        data = json.load(f)

    if data.get("tier5_code"):
        print(f"Skipping {data['project']}-{data['bug_id']}, tier5 already done")
        return

    print(f"Generating tier5 for {data['project']}-{data['bug_id']}...")
    
    try:
        tier5_code = generate_semantic_rewrite(data["buggy_code"], data["file_path"])
        data["tier5_code"] = tier5_code
        with open(data_json_path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Saved tier5 for {data['project']}-{data['bug_id']}")
        time.sleep(8)  # wait 8 seconds between calls to stay under rate limit
    except Exception as e:
        print(f"ERROR for {data['project']}-{data['bug_id']}: {e}")
        time.sleep(30)  # wait longer on error

if __name__ == "__main__":
    BUGS_DIR = "/Users/sunny/llm-bug-study/experiment/bugs"
    for bug_dir in sorted(os.listdir(BUGS_DIR)):
        data_path = os.path.join(BUGS_DIR, bug_dir, "data.json")
        if os.path.exists(data_path):
            process_bug(data_path)
    print("All tier5 rewrites done!")
