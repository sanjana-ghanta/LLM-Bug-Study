#!/usr/bin/env bash
# Run the whole study (Stage 1+2 detection and Stage 3 probes) on ANY OpenAI-compatible model,
# on N bugs per language (default 50 Java + 50 Python), with one command.
#
# Configure the model with four environment variables:
#   export MODEL_NAME=my-model              # short label for your result files (letters, digits, . _ -)
#   export MODEL_API_KEY=...                # API key
#   export MODEL_BASE_URL=https://.../v1    # OpenAI-compatible endpoint
#   export MODEL_ID=...                     # the exact model ID the endpoint expects
# (MODEL_NAME is optional: it defaults to MODEL_ID.)
#
# Then:
#   ./run_all_experiments.sh smoke          # 2-bug test per language, ~minutes, cleans up after itself
#   ./run_all_experiments.sh                # the full run on 50 bugs per language
#   ./run_all_experiments.sh -n 40          # the full run on any other number of bugs per language
# (or: bash run_all_experiments.sh -n 40)
#
# The bugs are a random sample of the usable bugs with a fixed seed (0), so every model
# run with the same N sees the same bugs. Safe to re-run: finished bugs are skipped.
# (Re-running with a larger N adds bugs but keeps the earlier results.)
#
# Optional environment variable:
#   REASONING_EFFORT=low     low|medium|high, or "none" to not pass the flag at all
#
# Output: results_<MODEL_NAME>.tgz (send this back). Logs are in logs_<MODEL_NAME>/.

set -uo pipefail
cd "$(dirname "$0")"

die() { echo "ERROR: $*" >&2; exit 1; }
say() { echo; echo "=== $* ($(date +%H:%M:%S))"; }

MODE=full
N=50
while [ $# -gt 0 ]; do
  case "$1" in
    smoke) MODE=smoke ;;
    -n|--num-bugs) [ $# -ge 2 ] || die "-n needs a number"; N=$2; shift ;;
    *) die "unknown argument '$1'. Usage: bash run_all_experiments.sh [smoke] [-n N]" ;;
  esac
  shift
done
case "$N" in ''|*[!0-9]*) die "-n must be a positive integer, got '$N'" ;; esac
[ "$N" -ge 1 ] || die "-n must be at least 1"

# ---------------------------------------------------------------- checks
for v in MODEL_API_KEY MODEL_BASE_URL MODEL_ID; do
  [ -n "${!v:-}" ] || die "$v is not set (see the 'export' lines at the top of this file)"
done
MODEL=${MODEL_NAME:-$(printf '%s' "$MODEL_ID" | tr -c 'A-Za-z0-9._-' '-')}
case "$MODEL" in ''|*[!A-Za-z0-9._-]*) die "MODEL_NAME may only contain letters, digits, '.', '_' and '-' (got '$MODEL')" ;; esac
export MODEL
python3 -c "import openai" 2>/dev/null || die "python package 'openai' missing: pip install --user openai"
grep -q -- "--num-bugs" scripts/run/run_tiered_detection.py \
  || die "the -n flag is missing from the runners: run 'git pull' first"

EFFORT=${REASONING_EFFORT:-low}
EFF=()
[ "$EFFORT" != "none" ] && EFF=(--reasoning-effort "$EFFORT")

LOGDIR="logs_${MODEL}"
OUT="results_${MODEL}.tgz"
export DET_MAX_TOKENS=32000
mkdir -p "$LOGDIR"

# ------------------------------------------------- register the model once
python3 - <<'EOF' || die "could not register the model in scripts/lib/config.py"
import os
name = os.environ["MODEL"]
p = "scripts/lib/config.py"
s = open(p).read()
marker = "# added by run_all_experiments.sh"
if f'"{name}"' in s:
    # an entry with this name exists: fine only if we created it (it reads the MODEL_* variables)
    i = s.index(f'"{name}"')
    block = s[i:i + 400]
    if "MODEL_API_KEY" not in block:
        raise SystemExit(f"ERROR: the name '{name}' is already used by another model in config.py. Choose a different MODEL_NAME.")
    print(f"model {name} already registered")
else:
    assert s.count("MODELS = {\n") == 1, "cannot find 'MODELS = {' in config.py"
    entry = f'''MODELS = {{
    "{name}": {{  {marker}
        "backend": "openai_compatible",
        "base_url": os.environ.get("MODEL_BASE_URL", ""),
        "model_id": os.environ.get("MODEL_ID", ""),
        "api_key_env": "MODEL_API_KEY",
    }},
'''
    open(p, "w").write(s.replace("MODELS = {\n", entry, 1))
    print(f"registered model {name}")
EOF

R_JAVA="results/java/results_fivetier_${MODEL}.csv"
R_PY="results/python/results_fivetier_python_${MODEL}.csv"
clean_results() {
  rm -f "$R_JAVA" "results/java/results_fivetier_${MODEL}_failures.json" \
        "$R_PY" "results/python/results_fivetier_python_${MODEL}_failures.json"
}

# run_detection <logsuffix> <N>: both languages in parallel on N bugs each; sets ERRS
run_detection() {
  local suffix=$1 n=$2
  python3 -u scripts/run/run_tiered_detection.py        --model "$MODEL" ${EFF[@]+"${EFF[@]}"} -n "$n" > "$LOGDIR/java_$suffix.log" 2>&1 &
  local p1=$!
  python3 -u scripts/run/run_tiered_detection_python.py --model "$MODEL" ${EFF[@]+"${EFF[@]}"} -n "$n" > "$LOGDIR/python_$suffix.log" 2>&1 &
  local p2=$!
  wait $p1 || echo "  (Java runner exited with an error, see $LOGDIR/java_$suffix.log)"
  wait $p2 || echo "  (Python runner exited with an error, see $LOGDIR/python_$suffix.log)"
  ERRS=$(cat "$LOGDIR/java_$suffix.log" "$LOGDIR/python_$suffix.log" | grep -c "Error calling" || true)
}

# ------------------------------------------------------------------ smoke
if [ "$MODE" = "smoke" ]; then
  if [ -e "$R_JAVA" ] || [ -e "$R_PY" ]; then
    die "results for $MODEL already exist. The smoke test would delete them; move them away first, or run without 'smoke' to resume."
  fi
  say "Smoke test of '$MODEL': 2 bugs per language"
  run_detection smoke 2
  rows_j=$( [ -f "$R_JAVA" ] && wc -l < "$R_JAVA" || echo 0 )
  rows_p=$( [ -f "$R_PY" ]   && wc -l < "$R_PY"   || echo 0 )
  echo "Result rows (incl. header): Java=$rows_j Python=$rows_p, API errors: $ERRS"
  grep -h "Error calling" "$LOGDIR"/java_smoke.log "$LOGDIR"/python_smoke.log | sort | uniq -c | head -5
  clean_results
  if [ "$ERRS" -eq 0 ] && [ "$rows_j" -gt 1 ] && [ "$rows_p" -gt 1 ]; then
    echo; echo "SMOKE TEST PASSED. Now run:  ./run_all_experiments.sh"
    exit 0
  fi
  echo; echo "SMOKE TEST FAILED. Send Sanjana the lines above and the files in $LOGDIR/."
  echo "Common fixes: wrong MODEL_ID / MODEL_BASE_URL / MODEL_API_KEY; 'max_tokens' or 'reasoning_effort' rejected."
  echo "If reasoning_effort is rejected, retry with:  REASONING_EFFORT=none ./run_all_experiments.sh smoke"
  exit 1
fi

# ------------------------------------------------------------------- full
say "Stage 1+2: detection of '$MODEL' on $N Java + $N Python bugs"
for pass in 1 2 3; do
  say "Detection pass $pass of up to 3"
  run_detection "pass$pass" "$N"
  echo "API errors in this pass: $ERRS"
  [ "$ERRS" -eq 0 ] && break
done
[ "$ERRS" -eq 0 ] || echo "WARNING: errors remain after 3 passes; see $LOGDIR/. Continuing anyway."

say "Stage 3: lists of missed bugs"
python3 scripts/run/find_tier2_misses.py java   "$MODEL" > "$LOGDIR/misses_java.log"   2>&1 || echo "  find_tier2_misses (java) failed, see $LOGDIR/misses_java.log"
python3 scripts/run/find_tier2_misses.py python "$MODEL" > "$LOGDIR/misses_python.log" 2>&1 || echo "  find_tier2_misses (python) failed, see $LOGDIR/misses_python.log"
wc -l results/tier2_misses/tier2_misses_java_${MODEL}.txt results/tier2_misses/tier2_misses_python_${MODEL}.txt 2>/dev/null

say "Stage 3: probes (Bug-ID Recall and Benchmark-Context Framing, both languages)"
pids=()
for s in run_experiment6_bugid_recall run_experiment6_bugid_recall_python \
         run_experiment7_context_framing run_experiment7_context_framing_python; do
  python3 -u "scripts/run/$s.py" --model "$MODEL" ${EFF[@]+"${EFF[@]}"} > "$LOGDIR/$s.log" 2>&1 &
  pids+=($!)
done
for p in "${pids[@]}"; do wait "$p" || echo "  (one probe run exited with an error; see $LOGDIR/)"; done
echo "Probe API errors: $(cat "$LOGDIR"/run_experiment*.log | grep -c 'Error calling' || true)"

say "Packing results"
find results \( -name "*_${MODEL}.csv" -o -name "*_${MODEL}_failures.json" -o -name "*_${MODEL}.txt" \) -print0 \
  | tar czf "$OUT" --null -T - "$LOGDIR"
ls -lh "$OUT"
echo
echo "DONE. Rows in main results (incl. header): Java=$(wc -l < "$R_JAVA" 2>/dev/null || echo 0)  Python=$(wc -l < "$R_PY" 2>/dev/null || echo 0)"
echo "Send $OUT to Sanjana (it contains no API key)."
