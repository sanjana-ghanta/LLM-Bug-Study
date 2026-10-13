# LLM-Bug-Study

Do LLMs suffer from data contamination on buggy-code benchmarks?
An empirical study on Defects4J (Java) and BugsInPy (Python) with three thinking models served by VT ARC.

| Model key | VT ARC model ID | Reasoning level |
|---|---|---|
| `glm-5.3-thinking` | `GLM-5.3-thinking-high` | high |
| `deepseek-v4-flash-thinking` | `DeepSeek-V4.1-Flash-thinking-max` | max |
| `gpt-oss-thinking` | `gpt-oss-120b-thinking-high` | high |

Reasoning level is set by the model ID in `scripts/lib/config.py` and is not matched across models.

## Design

**Stage 1 (baselines)**
- Tier 1: clean (patched) code. Correct answer: no bug.
- Tier 2: the real buggy code. Correct answer: bug.

**Stage 2 (only for bugs that passed Stage 1)**
- Tier 3: clean code with a synthetic bug injected. Scored only where Tier 1 was correct.
- Tier 4: the real bug in disguised (semantically rewritten) code. Scored only where Tier 2 was correct.
  Stored internally as "tier 5": `tier5_code_by_model` in each `data.json`. The disguise used for all models is currently written by GLM.

**Follow-up probes** (run on each model's own Tier 2 misses; whole file sent; files over 1,000 lines skipped)
- Experiment 6: names the benchmark, project and bug ID, asks for the bug line.
- Experiment 7: only says the file is from a public bug benchmark.
- Scoring: the reported line must equal the bug line exactly.

## Layout

```
data/bugs/<Project>_<id>/data.json      Java bugs (600; 573 usable)
data/pybugs/<project>_<id>/data.json    Python bugs (500)
scripts/run/                            experiment scripts
scripts/lib/                            llm_clients.py, config.py (model keys)
scripts/inject/                         tier 3 / tier 5 (disguise) generation
scripts/legacy/                         earlier experiment iterations (not part of the final pipeline)
results/java/, results/python/          result CSVs and failure counters
tier2_misses_<lang>_<model>.txt         bugs each model missed at Tier 2 (probe inputs)
make_tables.py                          builds the paper tables from the CSVs
summarize_probes.py                     probe summaries
rescore_exact.py, patch_effort.py, make_py_probes.py   one-off helpers
```

A bug is "usable" if its `data.json` has `original_bug_line`.
Each `data.json` holds `buggy_code`, `patched_code`, the tier 3 and tier 5 code and the bug line,
so the original benchmarks do not need to be downloaded to run anything.

## Setup

```bash
git clone --depth 1 https://github.com/sanjana-ghanta/LLM-Bug-Study.git
cd LLM-Bug-Study
export VT_ARC_API_KEY=your_key_here    # never commit the key
cd scripts && python3 -m lib.llm_clients glm-5.3-thinking   # smoke test
```

## Running experiments

Run inside `tmux`, from the repo root, logging with `tee`:

```bash
python3 -u scripts/run/run_tiered_detection.py --model glm-5.3-thinking 2>&1 | tee detect.log          # Java, Stage 1+2
python3 -u scripts/run/run_tiered_detection_python.py --model glm-5.3-thinking 2>&1 | tee detect.log   # Python
python3 scripts/run/find_tier2_misses.py java glm-5.3-thinking      # build the miss list for the probes
python3 -u scripts/run/run_experiment6_bugid_recall.py --model glm-5.3-thinking 2>&1 | tee exp6.log
python3 -u scripts/run/run_experiment7_context_framing.py --model glm-5.3-thinking 2>&1 | tee exp7.log
# Python probes: run_experiment6_bugid_recall_python.py / run_experiment7_context_framing_python.py
python3 make_tables.py | tee tables_out.txt
```

Options: `--project <name>` (detection), `--reasoning-effort low|medium|high` (all runner scripts).

## Things to know

- **Jobs resume.** Every result row is saved to CSV; rerunning the same command skips finished rows.
- **Detection is conditional.** Tier 3 runs only if Tier 1 was correct, Tier 4 only if Tier 2 was correct.
  After 3 failed passes an item is permanently "given up" (`*_failures.json`).
- **Output limit is 7,000 tokens.** Thinking models sometimes spend all of it reasoning and return nothing;
  those calls are not saved. DeepSeek and GPT-OSS are affected most.
- **Probe coverage is limited** by the 1,000-line file cap and by empty responses.
- **Nodes can kill jobs.** Check that a log's modification time is close to `date`; `tmux` sessions are per node.
- `make_tables.py` drops unusable bugs, removes duplicate rows (earliest kept) and scores probes by exact line.

## Known limitations

- Tier 4 disguises are written by GLM for all models (a self-preference / single-writer confound).
- The disguises are instructed to preserve behavior but are not verified.
- DeepSeek results are partial because of empty responses.

## Legacy

`scripts/legacy/` holds earlier experiment iterations, including the original pilot (45 Java and 50 Python bugs)
and a sycophancy challenge experiment. They are not part of the final pipeline.
