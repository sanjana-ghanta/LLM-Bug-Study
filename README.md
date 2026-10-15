# LLM-Bug-Study

Do LLMs suffer from data contamination on buggy-code benchmarks?
An empirical study on Defects4J (Java) and BugsInPy (Python) with three thinking models served by VT ARC.

| Model key | VT ARC model ID | Reasoning level |
|---|---|---|
| `glm-5.3-thinking` | `GLM-5.3-thinking-high` | high |
| `deepseek-v4-flash-thinking` | `DeepSeek-V4.1-Flash-thinking-low` | low |
| `gpt-oss-thinking` | `gpt-oss-120b-thinking-high` | high |

Reasoning level is set by the model ID in `scripts/lib/config.py` and is not matched across models.

## Design

**Stage 1 (baselines)**
- Tier 1: clean (patched) code. Correct answer: no bug.
- Tier 2: the real buggy code. Correct answer: bug.

**Stage 2 (only for bugs that passed Stage 1)**
- Tier 3: clean code with a synthetic bug injected. Scored only where Tier 1 was correct.
- Tier 4: the real bug in disguised (semantically rewritten) code. Scored only where Tier 2 was correct.
  Stored internally as "tier 5": `tier5_code_by_model` in each `data.json`. The disguise is written by Claude Sonnet 5.5 (`claude-sonnet-5-5`, key `claude-sonnet-win`). It rewrites only the +/-60-line window around the bug, the same window the other tiers show, so every tier sees matched context. The rewritten snippet has no line-number prefixes. Run Tier 4 with `TIER5_WRITER=claude-sonnet-win T5_NO_TRUNCATE=1`. Five bugs have no usable rewrite and are excluded: keras_16, keras_28, keras_32, Lang_19, Collections_17.

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
results/tier2_misses/tier2_misses_<lang>_<model>.txt         bugs each model missed at Tier 2 (probe inputs)
scripts/analysis/make_tables.py                          builds the paper tables from the CSVs
scripts/analysis/summarize_probes.py                     probe summaries
scripts/analysis/rescore_exact.py, scripts/analysis/patch_effort.py, scripts/analysis/make_py_probes.py   one-off helpers
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

Python 3.12; the detection and probe scripts need only `openai` (`anthropic` is optional, for the Claude backend and the rewrite scripts in `scripts/inject/`):

```bash
pip install -r requirements.txt
```

## Running on a fresh machine

1. `git clone --depth 1 https://github.com/sanjana-ghanta/LLM-Bug-Study.git && cd LLM-Bug-Study` (about 40 MB).
2. `pip install -r requirements.txt`.
3. Set the key for the model you use: `VT_ARC_API_KEY` (GLM, DeepSeek, GPT-OSS via VT ARC) or `ANTHROPIC_API_KEY` (Claude). Endpoints, model IDs and key variable names live in `scripts/lib/config.py`.
4. End-to-end check on 3 small bugs (about 10 calls):
   `TIER5_WRITER=claude-sonnet-win T5_NO_TRUNCATE=1 python3 scripts/run/run_tiered_detection_python.py --model glm-5.3-thinking --project PySnooper`
   If the repo's committed CSV already holds those cells the run only prints "already done"; delete `results/python/results_fivetier_python_glm-5.3-thinking__t5-claude-sonnet-win*` first to force real calls.
5. To add a model, add an entry to `MODELS` in `scripts/lib/config.py` (backend, base_url, model_id, api_key_env). No paths in the code are machine-specific.

ARC allows 20 concurrent requests per key; a full run of one model takes days at that limit.

## Running experiments

Run inside `tmux`, from the repo root, logging with `tee`:

```bash
python3 -u scripts/run/run_tiered_detection.py --model glm-5.3-thinking 2>&1 | tee detect.log          # Java, Stage 1+2
python3 -u scripts/run/run_tiered_detection_python.py --model glm-5.3-thinking 2>&1 | tee detect.log   # Python
python3 scripts/run/find_tier2_misses.py java glm-5.3-thinking      # build the miss list for the probes
python3 -u scripts/run/run_experiment6_bugid_recall.py --model glm-5.3-thinking 2>&1 | tee exp6.log
python3 -u scripts/run/run_experiment7_context_framing.py --model glm-5.3-thinking 2>&1 | tee exp7.log
# Python probes: run_experiment6_bugid_recall_python.py / run_experiment7_context_framing_python.py
python3 scripts/analysis/make_tables.py | tee tables_out.txt
```

Options: `--project <name>` (detection), `--reasoning-effort low|medium|high` (all runner scripts).
Environment variables: `TIER5_WRITER` (which Tier 4 rewrite to use), `TIER5_ONLY=1` (run only Tier 4), `T5_NO_TRUNCATE=1` (do not truncate Tier 4 snippets), `DET_MAX_TOKENS` (output budget, default 7000).

## Things to know

- **Jobs resume.** Every result row is saved to CSV; rerunning the same command skips finished rows.
- **Detection is conditional.** Tier 3 runs only if Tier 1 was correct, Tier 4 only if Tier 2 was correct.
  After 3 failed passes an item is permanently "given up" (`*_failures.json`).
- **Default output limit is 7,000 tokens** (`DET_MAX_TOKENS` overrides it; the scripts stream, so up to 12,000 works on ARC; non-streaming requests are capped at 8,000). Thinking models sometimes spend all of it reasoning and return nothing; those calls are retried, then given up and not saved. DeepSeek and GPT-OSS are affected most. Some DeepSeek Java and probe runs used 12,000; most DeepSeek runs used `--reasoning-effort low`.
- **Probe coverage is limited** by the 1,000-line file cap and by empty responses.
- **Nodes can kill jobs.** Check that a log's modification time is close to `date`; `tmux` sessions are per node.
- `scripts/analysis/make_tables.py` drops unusable bugs, removes duplicate rows (earliest kept) and scores probes by exact line.

## Known limitations

- **Tier 4 truncation bug (fixed).** The first Tier 4 runs had no center line, so the code was cut to the first 120 lines and often did not contain the bug (298 of 356 Java and 136 of 189 Python rewrites affected). Tier 4 was redone with matched-window rewrites. The old truncated results are kept only as a labelled ablation.
- **Tier 4 differs from Tiers 1-3 in view:** rewritten window, no line-number prefixes.
- **Single rewriter.** All disguises are written by Claude Sonnet 5.5. They are instructed to preserve the bug but are not verified.
- **Tier 3 is a rule-based mutation** at the first eligible location. It changes behaviour, and bugs with no eligible site are excluded from Tier 3.
- **Coverage is uneven.** DeepSeek (and some GPT-OSS Python cells) have many empty-response cells. Report accuracy with denominators.
- **Budgets and reasoning effort differ across runs** (see above).
- **Gating uses a snapshot of Tier 2.** Bugs that became Tier 2-correct later need one more Tier 4 pass.
- Probes skip files over 1,000 lines.

## Legacy

`scripts/legacy/` holds earlier experiment iterations, including the original pilot (45 Java and 50 Python bugs)
and a sycophancy challenge experiment. They are not part of the final pipeline.
