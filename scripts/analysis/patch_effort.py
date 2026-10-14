import re, shutil

FILES = [
    "scripts/run/run_tiered_detection_python.py",
    "scripts/run/run_experiment6_bugid_recall.py",
    "scripts/run/run_experiment7_context_framing.py",
]

STEPS = [
    ("add global", r'^(MAX_TOKENS = 7000.*)$',
     r'\1\nREASONING_EFFORT = None  # set from --reasoning-effort'),
    ("pass to call_llm", r'^(\s*)max_tokens=MAX_TOKENS,[ \t]*$',
     r'\1max_tokens=MAX_TOKENS,\n\1reasoning_effort=REASONING_EFFORT,'),
    ("add CLI flag",
     r'^(\s*)(parser\.add_argument\("--model", required=True, help="Model key from lib\.config\.MODELS"\))[ \t]*$',
     r'\1\2\n\1parser.add_argument("--reasoning-effort", default=None, choices=["low", "medium", "high"],\n\1                    help="Reasoning effort for models that support it")'),
    ("set global", r'^(\s*)(args = parser\.parse_args\(\))[ \t]*$',
     r'\1\2\n\1global REASONING_EFFORT\n\1REASONING_EFFORT = args.reasoning_effort'),
]

for path in FILES:
    src = open(path).read()
    if "REASONING_EFFORT" in src:
        print(f"{path}: already patched, skipping")
        continue
    out, problems = src, []
    for name, pat, repl in STEPS:
        out, n = re.subn(pat, repl, out, flags=re.M)
        if n != 1:
            problems.append(f"{name}: matched {n} times")
    if problems:
        print(f"{path}: NOT patched -> " + "; ".join(problems))
        continue
    shutil.copy(path, path + ".bak_effort")
    open(path, "w").write(out)
    print(f"{path}: patched (backup: {path}.bak_effort)")
