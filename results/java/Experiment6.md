# Experiment 6: Bug ID Recall Test

## Dataset

**25 active Chart bugs** from Defects4J (Chart_19 and Chart_20 excluded)

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
- Bug ID explicitly included in the prompt
- Forces a line number commitment

### Classification
 
| Tier | Response | Classification |
|------|----------|----------------|
| 1 (clean) | Gave a line number | `pattern_matched_clean` — recalled bug on clean code |
| 1 (clean) | Analysis but no LINE: | `malformed` — analyzed but didn't commit |
| 1 (clean) | No line, no analysis | `reasoned_no_bug` — correct |
| 2 (buggy) | Within ±5 of actual line | `correct` |
| 2 (buggy) | Different line number | `wrong` |
| 2 (buggy) | Analysis but no LINE: | `malformed` |
| 2 (buggy) | No line, no analysis | `none` |

### Model
Claude Haiku (`claude-haiku-4-5-20251001`)

> **Note:** This experiment was supposed to run on VT ARC's `gpt-oss-120b` model. However, the model returned empty responses so re-running with gpt-oss-120b is pending resolution of the ARC API issue.

---

## Results
 
### Tier 1 — clean/patched code (no bug exists)
 
| Result | Count | Rate |
|--------|-------|------|
| `pattern_matched_clean` — gave a line on clean code | 21/24 | 87.5% |
| `malformed` — gave analysis but no line number | 3/24 | 12.5% |
| `reasoned_no_bug` — correctl | 0/24 | 0% |
 
**Claude never once correctly answered on clean code.** Every single tier 1 response either gave a confident line number (87.5%) or gave a partial analysis without committing to a line (12.5%). Zero cases of correctly recognizing the code was clean.
 
### Tier 2 — buggy code (bug exists)
 
| Result | Count | Rate |
|--------|-------|------|
| `correct` — found the right line | 3/24 | 12.5% |
| `wrong` — gave a line but wrong | 18/24 | 75.0% |
| `malformed` — gave analysis but no line | 3/24 | 12.5% |
| `none` | 0/24 | 0% |
 
---

## Tier 1 vs Tier 2 Comparison

For bugs where Claude gave a line on both versions, how similar were the answers?

| Bug | Tier 1 line (clean) | Tier 2 line (buggy) | Actual line | T1-T2 diff |
|-----|--------------------|--------------------|-------------|------------|
| Chart_7 | 319 | 324 | 300 | 5 |
| Chart_8 | 126 | 124 | 175 | 2 |
| Chart_10 | 63 | 62 | 65 | 1 |
| Chart_23 | 446 | 453 | 434 | 7 |
| Chart_24 | 121 | 119 | 126 | 2 |

**5 out of 19 bugs (26.3%) where Claude gave nearly identical line numbers on both the clean AND buggy version.**

Chart_10 is the clearest example:
- Tier 1 (clean code, no bug): reported **line 63**
- Tier 2 (buggy code): reported **line 62**
- Actual bug: **line 65**

Claude reported almost the same line on both versions. If it were actually reading the code, the clean version should produce a completely different answer, the bug is gone. Instead it gave the same answer both times because it already most likley "knows" approximately where that bug is from training data.

### Cross-version consistency stats

| Metric | Count | Rate |
|--------|-------|------|
| Same line on clean AND buggy (within ±10) | 5/19 | 26.3% |
| Tier 1 (clean) answer within ±10 of actual bug line | 3/19 | 15.8% |

---


## Key Findings

**Finding 1: 87.5% pattern match rate on clean code proves retrieval behavior.**
When told the bug ID and asked "what line is the bug on?", Claude confidently reported a line 87.5% of the time on code where the bug no longer exists. A reasoning model would struggle on clean code, Claude doesn't, because it's recalling the bug location from training data.

**Finding 2: Correct attribution equals false positive rate.**
Claude found the correct line on buggy code 12.5% of the time, the same rate at which it correctly abstained on clean code (12.5%). This symmetry suggests the correct hits are also recalls, not genuine reasoning.

**Finding 3: 26.3% same answer on both versions.**
For over a quarter of bugs, Claude reported nearly identical line numbers on both the clean and buggy versions of the same file. This is impossible if it were analyzing the code, it means it's answering from memory.

**Finding 4: The search engine hypothesis is supported.**
Across all three metrics (87.5% pattern match, 26.3% cross-version consistency, 15.8% clean-code proximity to actual), the evidence points to the same conclusion: Claude is not analyzing the code. It is retrieving what it remembers about that bug ID from training data.

---

## Output file

| File | Description |
|------|-------------|
| `results/java/results_v5_chart.csv` | v5 results — Claude Haiku (48 data points) |
| `results/java/results_v5_gptoss_chart.csv` | v5 attempts — gpt-oss-120b (empty responses) |
