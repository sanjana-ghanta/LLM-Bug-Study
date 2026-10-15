#!/usr/bin/env python3
"""One-command runner: Tiers 1-4, with the Claude Sonnet 5.5 matched-window Tier 4.
Usage: python3 scripts/run/run_experiment.py --model glm-5.3-thinking --lang java [--project Chart,Lang]
       [--reasoning-effort low] [--max-tokens 12000]
Results: results/<lang>/results_fivetier[_python]_<model>__t5-claude-sonnet-win.csv
Summary: python3 scripts/analysis/quick_summary.py <that csv>"""
import argparse, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True)
ap.add_argument("--lang", required=True, choices=["java", "python"])
ap.add_argument("--project", default="all")
ap.add_argument("--reasoning-effort", choices=["low", "medium", "high"])
ap.add_argument("--max-tokens")
a = ap.parse_args()
script = "run_tiered_detection.py" if a.lang == "java" else "run_tiered_detection_python.py"
cmd = [sys.executable, "-u", os.path.join(HERE, script), "--model", a.model, "--project", a.project]
if a.reasoning_effort:
    cmd += ["--reasoning-effort", a.reasoning_effort]
env = dict(os.environ, TIER5_WRITER="claude-sonnet-win", T5_NO_TRUNCATE="1")
if a.max_tokens:
    env["DET_MAX_TOKENS"] = a.max_tokens
sys.exit(subprocess.call(cmd, env=env))
