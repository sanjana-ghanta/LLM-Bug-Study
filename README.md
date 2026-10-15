# LLM-Bug-Study

Do LLMs suffer from data contamination on buggy-code benchmarks?
An empirical study on Defects4J (Java) and BugsInPy (Python) with three thinking models served by VT ARC.

| Model key | VT ARC model ID | Reasoning level |
|---|---|---|
| `glm-5.3-thinking` | `GLM-5.3-thinking-high` | high |
| `deepseek-v4-flash-thinking` | `DeepSeek-V4.1-Flash-thinking-max` | `--reasoning-effort low` on most runs |
| `gpt-oss-thinking` | `gpt-oss-120b-thinking-high` | high |

Reasoning level is set by the model ID in `scripts/lib/config.py` (GLM, GPT-OSS) and, for DeepSeek, mostly by `--reasoning-effort low` per request. It is not matched across models.

## Design

**Stage 1 (baselines)**
- Tier 1: clean (patched) code. Correct answer: no bug.
- Tier 2: the real buggy code. Correct answer: bug.

**Stage 2 (only for bugs that passed Stage 1)**
- Tier 3: clean code with a synthetic bug injected. Scored only where Tier 1 was correct.
- Tier 4: the real bug in disguised (semantically rewritten) code. Scored only where Tier 2 was correct.
  Stored internally as "tier 5": `tier5_code_by_model` in each `data.json`. The disguise is written by Claude Sonnet 5.5 (`claude-sonnet-5-5`, key `claude-sonnet-win`). It rewrites only the +/-60-line window around the bug, the same window the other tiers show, so every tier sees matched context. The rewritten snippet has no line-number prefixes. Run Tier 4 with `--tier4-writer claude-sonnet-win --no-truncate`. Five bugs have no usable rewrite and are excluded: keras_16, keras_28, keras_32, Lang_19, Collections_17.

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
   `python3 scripts/run/run_experiment.py --model glm-5.3-thinking --lang python --project PySnooper`, then `python3 scripts/analysis/quick_summary.py results/python/results_fivetier_python_glm-5.3-thinking__t5-claude-sonnet-win.csv` for per-tier accuracy
   If the repo's committed CSV already holds those cells the run only prints "already done"; delete `results/python/results_fivetier_python_glm-5.3-thinking__t5-claude-sonnet-win*` first to force real calls.
5. To add a model (for example an open model served locally with vLLM or Ollama), add an entry to `MODELS` in `scripts/lib/config.py`:
   ```python
   "my-open-model": {
       "backend": "openai_compatible",
       "base_url": "http://localhost:8000/v1",   # vLLM default; Ollama: http://localhost:11434/v1
       "model_id": "<exact model name your server reports>",
       "api_key_env": "OPEN_MODEL_API_KEY",
   },
   ```
   Then run it:
   ```bash
   export OPEN_MODEL_API_KEY=dummy   # local servers ignore the key, but the variable must be set
   python3 scripts/run/run_experiment.py --model my-open-model --lang java --max-tokens 4000
   ```
   Lower `--max-tokens` for models with a small context window (prompt plus output must fit), and read a few raw responses in the CSV first: scoring needs `VERDICT: BUG` or `VERDICT: NO BUG` in the answer. Add `--with-probes` to also run Exp6 and Exp7 on the model's Tier 2 misses (the probes send whole files of up to 1,000 lines, so the model needs a large enough context window), and `--lang both` to run Java and Python. Other options: `--project Chart,Lang`, `--reasoning-effort low|medium|high` (only for models that support it). No paths in the code are machine-specific.

ARC allows 20 concurrent requests per key.

## Running experiments

Run inside `tmux`, from the repo root, logging with `tee`:

```bash
python3 -u scripts/run/run_experiment.py --model glm-5.3-thinking --lang java   2>&1 | tee detect.log   # Java, Tiers 1-4
python3 -u scripts/run/run_experiment.py --model glm-5.3-thinking --lang python 2>&1 | tee detect.log   # Python, Tiers 1-4
python3 -u scripts/run/run_experiment.py --model glm-5.3-thinking --lang both --with-probes 2>&1 | tee run.log   # everything for one model: Tiers 1-4, Tier 2 miss list, Exp6, Exp7
python3 scripts/run/find_tier2_misses.py java glm-5.3-thinking      # build the miss list for the probes
python3 -u scripts/run/run_experiment6_bugid_recall.py --model glm-5.3-thinking 2>&1 | tee exp6.log
python3 -u scripts/run/run_experiment7_context_framing.py --model glm-5.3-thinking 2>&1 | tee exp7.log
# Python probes: run_experiment6_bugid_recall_python.py / run_experiment7_context_framing_python.py
python3 scripts/analysis/make_tables.py | tee tables_out.txt   # main tables, plus an "Additional models" section for any other model run with run_experiment.py
python3 scripts/analysis/quick_summary.py results/java/results_fivetier_glm-5.3-thinking__t5-claude-sonnet-win.csv   # per-tier accuracy for one results file
```

## Things to know

- **Jobs resume.** Every result row is saved to CSV; rerunning the same command skips finished rows.
- **Detection is conditional.** Tier 3 runs only if Tier 1 was correct, Tier 4 only if Tier 2 was correct.
  After 3 failed passes an item is permanently "given up" (`*_failures.json`).
- **Probe coverage is limited** by the 1,000-line file cap and by empty responses.
- **Nodes can kill jobs.** Check that a log's modification time is close to `date`; `tmux` sessions are per node.
- `scripts/analysis/make_tables.py` drops unusable bugs, removes duplicate rows (earliest kept) and scores probes by exact line.

## Known limitations
- **Coverage is uneven.** DeepSeek (and some GPT-OSS Python cells) have many empty-response cells. Report accuracy with denominators.
- **Budgets and reasoning effort differ across runs** (see above).
- **Gating uses a snapshot of Tier 2.** Bugs that became Tier 2-correct later need one more Tier 4 pass.
- Probes skip files over 1,000 lines.

## Legacy

`scripts/legacy/` holds earlier experiment iterations, including the original pilot (45 Java and 50 Python bugs)
and a sycophancy challenge experiment. They are not part of the final pipeline.
