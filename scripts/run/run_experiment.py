#!/usr/bin/env python3
"""One-command runner for a single model.
Tiers 1-4 (Tier 4 = Claude Sonnet 5.5 matched-window rewrite). With --with-probes it also builds the
model's Tier 2 miss list and runs Exp6 (bug-ID recall) and Exp7 (context framing).
Usage: python3 scripts/run/run_experiment.py --model glm-5.3-thinking --lang java|python|both [--project Chart,Lang]
       [--reasoning-effort low] [--max-tokens 12000] [--with-probes]
Summary: python3 scripts/analysis/quick_summary.py <results csv>   or   python3 scripts/analysis/make_tables.py"""
import argparse, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True)
ap.add_argument("--lang", required=True, choices=["java", "python", "both"])
ap.add_argument("--project", default="all")
ap.add_argument("--reasoning-effort", choices=["low", "medium", "high"])
ap.add_argument("--max-tokens")
ap.add_argument("--with-probes", action="store_true")
a = ap.parse_args()

def run(cmd, env):
    print("\n$ " + " ".join(cmd), flush=True)
    rc = subprocess.call(cmd, env=env)
    if rc != 0:
        sys.exit(rc)

base_env = dict(os.environ)
if a.max_tokens:
    base_env["DET_MAX_TOKENS"] = a.max_tokens
tier_env = dict(base_env, TIER5_WRITER="claude-sonnet-win", T5_NO_TRUNCATE="1")
effort = ["--reasoning-effort", a.reasoning_effort] if a.reasoning_effort else []

for lang in (["java", "python"] if a.lang == "both" else [a.lang]):
    sfx = "" if lang == "java" else "_python"
    det = "run_tiered_detection.py" if lang == "java" else "run_tiered_detection_python.py"
    run([sys.executable, "-u", os.path.join(HERE, det), "--model", a.model, "--project", a.project] + effort, tier_env)
    if a.with_probes:
        run([sys.executable, os.path.join(HERE, "find_tier2_misses.py"), lang, a.model], base_env)
        for n, name in (("6", "run_experiment6_bugid_recall"), ("7", "run_experiment7_context_framing")):
            run([sys.executable, "-u", os.path.join(HERE, f"{name}{sfx}.py"), "--model", a.model] + effort, base_env)
