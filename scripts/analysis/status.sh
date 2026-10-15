cd ~/llm-bug-study
echo "== now $(date +%H:%M) =="
echo "-- logs written in the last 15 min (active) --"
find . -maxdepth 1 -name '*.log' -mmin -15 -printf '%TH:%TM  %f\n' | sort
echo "-- Java GPT-OSS Claude Tier 4 CSV (runs on another node) --"
ls -l --time-style=+%H:%M results/java/results_fivetier_gpt-oss-thinking__t5-claude-sonnet.csv | awk '{print $6, $7}'
echo; python3 scripts/analysis/completeness.py
echo; echo "-- probe coverage --"; python3 scripts/analysis/probe_coverage.py
