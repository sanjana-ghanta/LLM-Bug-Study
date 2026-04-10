import json
import os
import re

def inject_off_by_one(code):
    """Swap < and <= in for loops."""
    lines = code.splitlines()
    for i, line in enumerate(lines):
        if "for(" in line or "for (" in line:
            if "<=" in line:
                lines[i] = line.replace("<=", "<", 1)
                return "\n".join(lines), i+1, "off_by_one"
            elif "<" in line:
                lines[i] = line.replace("<", "<=", 1)
                return "\n".join(lines), i+1, "off_by_one"
    return None, None, None

def inject_operator_swap(code):
    """Swap + and - in expressions."""
    lines = code.splitlines()
    for i, line in enumerate(lines):
        if "return" in line or "=" in line:
            if " + " in line:
                lines[i] = line.replace(" + ", " - ", 1)
                return "\n".join(lines), i+1, "operator_swap"
            elif " - " in line:
                lines[i] = line.replace(" - ", " + ", 1)
                return "\n".join(lines), i+1, "operator_swap"
    return None, None, None

def inject_boolean_logic(code):
    """Swap && and || in boolean expressions."""
    lines = code.splitlines()
    for i, line in enumerate(lines):
        if "if(" in line or "if (" in line or "while(" in line:
            if "&&" in line:
                lines[i] = line.replace("&&", "||", 1)
                return "\n".join(lines), i+1, "boolean_logic"
            elif "||" in line:
                lines[i] = line.replace("||", "&&", 1)
                return "\n".join(lines), i+1, "boolean_logic"
    return None, None, None

def inject_spm(code):
    """Try each mutation type and return the first that works."""
    for fn in [inject_off_by_one, inject_operator_swap, inject_boolean_logic]:
        mutated, line_no, mut_type = fn(code)
        if mutated:
            return mutated, line_no, mut_type
    return None, None, None

def process_bug(data_json_path):
    with open(data_json_path) as f:
        data = json.load(f)

    patched_code = data["patched_code"]
    buggy_code = data["buggy_code"]

    # Tier 3: patched + SPM
    t3_code, t3_line, t3_type = inject_spm(patched_code)
    # Tier 4: buggy + SPM
    t4_code, t4_line, t4_type = inject_spm(buggy_code)

    data["tier3_code"] = t3_code
    data["tier3_mutation_line"] = t3_line
    data["tier3_mutation_type"] = t3_type
    data["tier4_code"] = t4_code
    data["tier4_mutation_line"] = t4_line
    data["tier4_mutation_type"] = t4_type

    with open(data_json_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Done: {data_json_path} | T3: {t3_type} @ line {t3_line} | T4: {t4_type} @ line {t4_line}")

if __name__ == "__main__":
    BUGS_DIR = "/Users/sunny/llm-bug-study/experiment/bugs"
    for bug_dir in sorted(os.listdir(BUGS_DIR)):
        data_path = os.path.join(BUGS_DIR, bug_dir, "data.json")
        if os.path.exists(data_path):
            process_bug(data_path)
    print("All SPMs injected!")
