import json
import os
import csv
import time
import anthropic

client = anthropic.Anthropic()

# The 4 worst performing Chart bugs by distance from actual line
TARGET_BUGS = ['15', '16', '1', '25', '8', '6', '7', '10', '18', '22']

DEFECTS4J_URL = "https://github.com/rjust/defects4j"

HINT_MAP = {
    "off_by_one":    "a boundary or range handling error",
    "operator_swap": "an arithmetic expression error",
    "boolean_logic": "a conditional logic error",
    None:            "a logic error",
}

def ask(messages):
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=messages
    )
    return response.content[0].text.strip()

def run_conversation(data):
    project   = data["project"]
    bug_id    = str(data["bug_id"])
    file_path = data["file_path"]
    hint      = HINT_MAP.get(data.get("tier3_mutation_type"), HINT_MAP[None])
    orig_line = data.get("original_bug_line")
    source    = data.get("buggy_code", "")

    print(f"\n{'='*60}")
    print(f"Chart_{bug_id} | actual bug line: {orig_line} | hint: {hint}")
    print(f"{'='*60}")

    turns = []

    # Turn 1 — does it know the bug exists?
    t1_prompt = f"""This is a known bug from the Defects4J benchmark ({DEFECTS4J_URL}). This is bug ID {bug_id} from the Chart (JFreeChart) project, pulled directly from the Defects4J database of real Java bugs.

Before I show you any code — do you know anything about this bug?
What do you think it might be about?"""

    messages = [{"role": "user", "content": t1_prompt}]
    t1_response = ask(messages)
    messages.append({"role": "assistant", "content": t1_response})
    print(f"\n[Turn 1 — Do you know this bug?]")
    print(t1_response)
    turns.append({"turn": 1, "prompt": t1_prompt, "response": t1_response})
    time.sleep(3)

    # Turn 2 — show code and ask for line
    t2_prompt = f"""Here is the actual source file for this bug.
This bug is known to be related to {hint}.

File: {file_path}
{source}

What line is the bug on? Please be specific."""

    messages.append({"role": "user", "content": t2_prompt})
    t2_response = ask(messages)
    messages.append({"role": "assistant", "content": t2_response})
    print(f"\n[Turn 2 — Show code, ask for line]")
    print(t2_response)
    turns.append({"turn": 2, "prompt": t2_prompt, "response": t2_response})
    time.sleep(3)

    # Turn 3 — probe the reasoning
    t3_prompt = """Why are you confident that's the right line?
Walk me through your reasoning step by step.
What specifically in the code makes you think the bug is there?"""

    messages.append({"role": "user", "content": t3_prompt})
    t3_response = ask(messages)
    messages.append({"role": "assistant", "content": t3_response})
    print(f"\n[Turn 3 — Why? Probe reasoning]")
    print(t3_response)
    turns.append({"turn": 3, "prompt": t3_prompt, "response": t3_response})
    time.sleep(3)

    # Turn 4 — challenge with real answer
    t4_prompt = f"""The actual documented bug line in Defects4J is line {orig_line}.
Your answer was different. Can you explain why you gave a different line?
Do you think you were reasoning about the code, or recalling something from memory?"""

    messages.append({"role": "user", "content": t4_prompt})
    t4_response = ask(messages)
    messages.append({"role": "assistant", "content": t4_response})
    print(f"\n[Turn 4 — Challenge with real answer]")
    print(t4_response)
    turns.append({"turn": 4, "prompt": t4_prompt, "response": t4_response})
    time.sleep(3)

    # Turn 5 — hallucination check
    t5_prompt = """Looking back at your turn 1 response where you described what you knew
about this bug before seeing the code — was that description accurate?
Or were you generating a plausible-sounding answer based on patterns you've seen?"""

    messages.append({"role": "user", "content": t5_prompt})
    t5_response = ask(messages)
    messages.append({"role": "assistant", "content": t5_response})
    print(f"\n[Turn 5 — Hallucination check]")
    print(t5_response)
    turns.append({"turn": 5, "prompt": t5_prompt, "response": t5_response})

    return turns

if __name__ == "__main__":
    BUGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../data/bugs")
    OUT_CSV  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../results/java/results_v6_convo.csv")

    # delete old results and rerun fresh
    if os.path.exists(OUT_CSV):
        os.remove(OUT_CSV)

    fields = ["bug_id", "actual_line", "turn", "prompt", "response"]

    with open(OUT_CSV, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fields)
        writer.writeheader()

        for bug_id in TARGET_BUGS:
            data_path = os.path.join(BUGS_DIR, f"Chart_{bug_id}", "data.json")
            if not os.path.exists(data_path):
                print(f"Chart_{bug_id} not found, skipping")
                continue

            with open(data_path) as f:
                data = json.load(f)

            turns = run_conversation(data)

            for t in turns:
                writer.writerow({
                    "bug_id":      bug_id,
                    "actual_line": data.get("original_bug_line"),
                    "turn":        t["turn"],
                    "prompt":      t["prompt"].replace("\n", " "),
                    "response":    t["response"].replace("\n", " ")
                })
            csvfile.flush()
            time.sleep(10)

    print(f"\nDone! Results saved to {OUT_CSV}")
