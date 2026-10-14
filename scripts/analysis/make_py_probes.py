import re
for name, out in [("run_experiment6_bugid_recall", "run_experiment6_bugid_recall_python"),
                  ("run_experiment7_context_framing", "run_experiment7_context_framing_python")]:
    s = open(f"scripts/run/{name}.py").read()
    def sub(old, new):
        global s
        assert old in s, f"{name}: missing {old!r}"
        s = s.replace(old, new)
    sub('"data/bugs"', '"data/pybugs"')
    sub('"results/java"', '"results/python"')
    sub("tier2_misses_java_", "tier2_misses_python_")
    sub("results_exp6_bugid_recall_" if "exp6" in name or "6" in name else "results_exp7_context_framing_",
        ("results_exp6_bugid_recall_python_" if "6" in name else "results_exp7_context_framing_python_"))
    if "Defects4J" in s:
        s = s.replace("Defects4J", "BugsInPy")
    # tolerate missing keys in the Python data.json
    s = s.replace('bug_id = str(data["bug_id"])', 'bug_id = str(data.get("bug_id", bug_dir.split("_")[-1]))')
    s = s.replace('file_path = data["file_path"]', 'file_path = data.get("file_path", bug_dir)')
    s = s.replace('project = data["project"]', 'project = data.get("project", bug_dir.rsplit("_", 1)[0])')
    # reasoning-effort flag (only if the earlier patch is not already there)
    if "REASONING_EFFORT" not in s:
        s = s.replace("MAX_TOKENS = 7000", "MAX_TOKENS = 7000\nREASONING_EFFORT = None", 1)
        s = s.replace("max_tokens=MAX_TOKENS,", "max_tokens=MAX_TOKENS,\n                reasoning_effort=REASONING_EFFORT,", 1)
        s = re.sub(r'(parser\.add_argument\("--model"[^\n]*\n)',
                   r'\1    parser.add_argument("--reasoning-effort", default=None, choices=["low", "medium", "high"])\n', s, 1)
        s = s.replace("args = parser.parse_args()", "args = parser.parse_args()\n    global REASONING_EFFORT\n    REASONING_EFFORT = args.reasoning_effort", 1)
    open(f"scripts/run/{out}.py", "w").write(s)
    print("wrote", out)
