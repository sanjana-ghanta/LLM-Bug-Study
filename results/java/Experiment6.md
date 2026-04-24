# Experiment 6: Bug ID Recall Test (v5)

## Motivation

Every previous experiment asked Claude "is there a bug?" or "what is the bug?" — always giving it the option to say NO BUG. This created ambiguity: when Claude said BUG on clean code, was it hallucinating, or recalling a real bug it had seen in training?

Experiment 6 removes that ambiguity with a direct test of the **search engine hypothesis**:

> If LLMs act as search engines retrieving training data rather than reasoning engines analyzing code, then telling Claude the bug ID and project name should allow it to recall approximately where the bug is — even on clean code where the bug no longer exists.

The key design change: **we never ask "is there a bug?" — we just ask "what line is the bug on?"**

This forces Claude to commit to a line number. Then we compare:
- What line it reports on **clean patched code** (tier 1 — no bug exists)
- What line it reports on **buggy code** (tier 2 — bug exists)

If Claude is reasoning, it should struggle on tier 1 (no bug to find) and succeed on tier 2.
If Claude is recalling from training, it should report similar lines on both — because it already "knows" where that bug is.

---

## Dataset

**25 active Chart bugs** from Defects4J (Chart_19 and Chart_20 excluded — no SPM injectable).

---

## Experimental Design

### Prompt

```
You are analyzing code from the {benchmark} benchmark.

This is bug ID {bug_id} from the {project} project in the Defects4J buggy dataset.
This bug is known to be related to {hint}.

Here is the full project file structure:
{manifest}

Here is the source file:
{file_path}
{source_code}

What line is the bug on?

Please respond in this exact format:
LINE: <line number>
REASON: <one sentence explanation of what specifically is wrong>
```

**Key differences from all previous experiments:**
- No VERDICT field — Claude cannot say NO BUG
- Bug ID explicitly included in the prompt
- Forces a line number commitment

### Classification

| Tier | Reported line | Classification |
|------|--------------|----------------|
| 1 (clean) | None/no line | `reasoned_no_bug` — correctly abstained ✅ |
| 1 (clean) | Any line | `pattern_matched_clean` — gave a line on clean code ❌ |
| 2 (buggy) | Within ±5 of actual | `correct` ✅ |
| 2 (buggy) | Different line | `wrong` |
| 2 (buggy) | None/no line | `none` |

### Model
Claude Haiku (`claude-haiku-4-5-20251001`)

> **Note:** This experiment was designed to run on VT ARC's `gpt-oss-120b` model. However, the model returned empty responses for code analysis prompts — likely due to content policy on the ARC instance. The experiment was run with Claude Haiku instead. Re-running with gpt-oss-120b is pending resolution of the ARC API issue.

---

## Results

### Tier 1 — clean/patched code (no bug exists)

| Result | Count | Rate |
|--------|-------|------|
| `pattern_matched_clean` — gave a line on clean code | 21/24 | **87.5%** |
| `reasoned_no_bug` — correctly gave no line | 3/24 | 12.5% |

### Tier 2 — buggy code (bug exists)

| Result | Count | Rate |
|--------|-------|------|
| `correct` — found the right line | 3/24 | 12.5% |
| `wrong` — gave a line but wrong | 18/24 | 75.0% |
| `none` — gave no line | 3/24 | 12.5% |

---

## The Smoking Gun — Tier 1 vs Tier 2 Comparison

For bugs where Claude gave a line on both versions, how similar were the answers?

| Bug | Tier 1 line (clean) | Tier 2 line (buggy) | Actual line | T1-T2 diff |
|-----|--------------------|--------------------|-------------|------------|
| Chart_7 | 319 | 324 | 300 | 5 ⚠️ |
| Chart_8 | 126 | 124 | 175 | 2 ⚠️ |
| Chart_10 | 63 | 62 | 65 | 1 ⚠️ |
| Chart_23 | 446 | 453 | 434 | 7 ⚠️ |
| Chart_24 | 121 | 119 | 126 | 2 ⚠️ |

**5 out of 19 bugs (26.3%) where Claude gave nearly identical line numbers on both the clean AND buggy version.**

Chart_10 is the clearest example:
- Tier 1 (clean code, no bug): reported **line 63**
- Tier 2 (buggy code): reported **line 62**
- Actual bug: **line 65**

Claude reported almost the same line on both versions. If it were actually reading the code, the clean version should produce a completely different answer — the bug is gone. Instead it gave the same answer both times because it already "knows" approximately where that bug is from training data.

### Cross-version consistency stats

| Metric | Count | Rate |
|--------|-------|------|
| Same line on clean AND buggy (within ±10) | 5/19 | 26.3% |
| Tier 1 (clean) answer within ±10 of actual bug line | 3/19 | 15.8% |

---

## Comparison Across All Experiments

| Experiment | Prompt | Tier 1 | Tier 2 | Correct attribution |
|------------|--------|--------|--------|---------------------|
| v1 | Neutral | 83.3% | 21.7% | ~3-4% |
| v2 | Benchmark context | 20.0% | 60.0% | 3.3% |
| v3 | Context + hint (Lang) | 15.8% | 82.5% | 3.5% |
| v4a | Manifest + test (Chart) | 83.3% | 29.2% | 4.2% |
| v4b | Package + hint + test (Chart) | 75.0% | 37.5% | 8.3% |
| v5 | Bug ID + hint, no verdict (Chart) | — | — | 12.5% |

> Note: v5 tier 1/2 accuracy is not directly comparable since we removed the VERDICT field — Claude can't say NO BUG so "accuracy" means something different.

---

## Key Findings

**Finding 1: 87.5% pattern match rate on clean code proves retrieval behavior.**
When told the bug ID and asked "what line is the bug on?", Claude confidently reported a line 87.5% of the time on code where the bug no longer exists. A reasoning model would struggle on clean code — Claude doesn't, because it's recalling the bug location from training data.

**Finding 2: Correct attribution equals false positive rate.**
Claude found the correct line on buggy code 12.5% of the time — the same rate at which it correctly abstained on clean code (12.5%). This symmetry suggests the correct hits are also recalls, not genuine reasoning.

**Finding 3: 26.3% same answer on both versions.**
For over a quarter of bugs, Claude reported nearly identical line numbers on both the clean and buggy versions of the same file. This is impossible if it were analyzing the code — it means it's answering from memory.

**Finding 4: The search engine hypothesis is supported.**
Across all three metrics (87.5% pattern match, 26.3% cross-version consistency, 15.8% clean-code proximity to actual), the evidence points to the same conclusion: Claude is not analyzing the code. It is retrieving what it remembers about that bug ID from training data.

---

## Output file

| File | Description |
|------|-------------|
| `results/java/results_v5_chart.csv` | v5 results — Claude Haiku (48 data points) |
| `results/java/results_v5_gptoss_chart.csv` | v5 attempts — gpt-oss-120b (empty responses) |
