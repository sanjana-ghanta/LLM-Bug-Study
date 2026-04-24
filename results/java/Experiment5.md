# Experiment 5: Full Project Context with Test Cases (v4)

## Dataset

**26 active Chart bugs** from Defects4J (JFreeChart project). No deprecated bugs.

**Why Chart?**
- Smallest complete project in Defects4J (26 bugs)
- 654 Java source files — small enough to work with, large enough to be realistic
- Existing results from experiment 1 for comparison

---

## Experimental Design

### Two variants

#### v4a — file manifest + test file
- Full list of all 654 project file paths (manifest)
- Single changed source file (no truncation)
- Full test file for the triggering test case

#### v4b — package files + type hint + test file
- Full file manifest
- Single changed source file
- All other Java files in the same package as the changed file
- Type hint derived from SPM mutation type (same as v3)
- Full test file

### Prompts

**v4a prompt:**
```
You are analyzing code from the {benchmark} benchmark.

A bug is defined as a defect in the code that causes one or more test cases to fail.

Given the project structure, the source file under investigation, and the test cases
below, can you identify if there is a bug?

Please respond in this exact format:
VERDICT: BUG or NO BUG
LINE: <file path and line number where the bug is, or NONE if no bug>
REASON: <one sentence explanation of what specifically is wrong>

---
PROJECT STRUCTURE ({project}):
{manifest}

---
SOURCE FILE: {file_path}
{source_code}

---
TEST FILE: {test_class}
{test_code}
```

**v4b prompt:**
```
You are analyzing code from the {benchmark} benchmark.

A bug is defined as a defect in the code that causes one or more test cases to fail.

This code contains a known issue related to {hint}.

Given the project structure, the source file under investigation, its related package
files, and the test cases below, can you identify if there is a bug?

Please respond in this exact format:
VERDICT: BUG or NO BUG
LINE: <file path and line number where the bug is, or NONE if no bug>
REASON: <one sentence explanation of what specifically is wrong>

---
PROJECT STRUCTURE ({project}):
{manifest}

---
SOURCE FILE UNDER INVESTIGATION: {file_path}
{source_code}

---
RELATED PACKAGE FILES:
{package_files}

---
TEST FILE: {test_class}
{test_code}
```

### Key differences from previous experiments

| | Exp 1 (v1) | Exp 3 (v2) | Exp 4 (v3) | Exp 5a (v4a) | Exp 5b (v4b) |
|---|---|---|---|---|---|
| Benchmark context | No | Yes | Yes | Yes | Yes |
| Type hint | No | No | Yes | No | Yes |
| File manifest | No | No | No | Yes | Yes |
| Package files | No | No | No | No | Yes |
| Test file | No | No | No | Yes | Yes |
| Tiers | 1-5 | 1-5 | 1-5 | 1-2 only | 1-2 only |
| Project | Lang/Math/Chart | Mixed | Lang | Chart | Chart |
| Model | Sonnet/Haiku | Sonnet | Haiku | Haiku | Haiku |

---

## Results

### v4a — file manifest + test file

| Tier | Description | Correct | Total | Accuracy |
|------|-------------|---------|-------|----------|
| 1 | Patched clean code | 20 | 24 | 83.3% |
| 2 | Original buggy code | 7 | 24 | 29.2% |

**Bug attribution (tier 2):**

| | Count | Rate |
|---|---|---|
| Found actual documented bug | 1/24 | 4.2% |
| Found something else | 9/24 | 37.5% |
| No bug reported | 14/24 | 58.3% |

### v4b — package files + type hint + test file

| Tier | Description | Correct | Total | Accuracy |
|------|-------------|---------|-------|----------|
| 1 | Patched clean code | 18 | 24 | 75.0% |
| 2 | Original buggy code | 9 | 24 | 37.5% |

**Bug attribution (tier 2):**

| | Count | Rate |
|---|---|---|
| Found actual documented bug | 2/24 | 8.3% |
| Found something else | 7/24 | 29.2% |
| No bug reported | 15/24 | 62.5% |

---

## Comparison Across All Experiments

| Experiment | Prompt | Tier 1 | Tier 2 | Found correct bug |
|------------|--------|--------|--------|-------------------|
| v1 | Neutral | 83.3% | 21.7% | ~3-4% |
| v2 | Benchmark context | 20.0% | 60.0% | 3.3% |
| v3 | Context + hint (Lang 59) | 15.8% | 82.5% | 3.5% |
| v4a | Full manifest + test (Chart) | 83.3% | 29.2% | 4.2% |
| v4b | Package files + hint + test (Chart) | 75.0% | 37.5% | **8.3%** |

---

## Review of Claude's Reasoning (v4b, tier 2)

Claude's reasoning quality was noticeably better with package context. Several bugs were correctly identified with detailed technical explanations:

| Bug | File | Reported line | Actual line | Assessment |
|-----|------|--------------|-------------|------------|
| Chart_1 | AbstractCategoryItemRenderer.java | 1327 | 1797 | Correct logic — inverted null check `if (dataset != null)` should be `if (dataset == null)` |
| Chart_3 | TimeSeries.java | 859 | 1056 | Plausible — `minIgnoreNaN` used instead of `maxIgnoreNaN` for `maxY` |
| Chart_4 | XYPlot.java | 2632 | 4492 | Plausible — wrong variable name in null check (Range vs Domain markers) |
| Chart_7 | TimePeriodValues.java | 296 | 300 | **Correct** — `minMiddleIndex` used instead of `maxMiddleIndex` (within ±5) |
| Chart_8 | Week.java | 122 | 175 | Plausible — `&&` should be `\|\|` in range validation |
| Chart_10 | StandardToolTipTagFragmentGenerator.java | 62 | 65 | **Correct** — missing HTML escaping (within ±5) |
| Chart_18 | DefaultKeyedValues.java | 309 | unknown | Plausible — `rebuildIndex()` not called on last element removal |
| Chart_24 | GrayPaintScale.java | 127 | unknown | Likely correct — clamped variable `v` unused, original `value` used instead |
| Chart_26 | Axis.java | 1119 | unknown | Ambiguous — operator precedence in center calculation |

Of 9 "other" verdicts: 2 confirmed correct, 5 plausible real bugs, 1 ambiguous, 1 wrong.

---

## Cross-Match Analysis

Testing whether Claude's "other" verdicts correspond to different documented bugs in the same file (temporal cross-referencing hypothesis).

**Result: 0/9 cross-matches (0.0%)**

Chart has fewer shared-file bugs than Lang so this was expected to be low. Combined with the Lang result (4.3%), the hypothesis does not hold. Claude is not finding future/past bugs from the same codebase.

---

## Key Findings

**Finding 1: Package context produced the best attribution rate across all experiments (8.3%).**
Giving Claude the full package, not just the changed file, helped it understand the surrounding code structure and produce more grounded bug reports.

**Finding 2: Tier 1 accuracy recovered with v4a (83.3%) but dipped slightly with v4b (75.0%).**
Without the type hint (v4a), Claude correctly identifies clean code at the same rate as v1. The type hint reintroduces some false positives.

**Finding 3: The "none" rate is high in both v4 variants (58-62%).**
With a large amount of context, Claude often says NO BUG rather than guessing, the opposite of v2/v3 where benchmark context pushed it toward saying BUG. This suggests Claude is more cautious when it has more to read.

**Finding 4: When Claude does find a bug in v4b, the reasoning is qualitatively better.**
Even when the line number is off, Claude's explanations are technically detailed, reference the test case, and often correctly describe the nature of the defect. The gap between attribution accuracy (8.3%) and reasoning quality is larger than in earlier experiments.

**Finding 5: More context ≠ more correct verdicts overall.**
v4b has the best attribution but only 37.5% tier 2 accuracy — worse than v2 (60%) and v3 (82.5%). The trade-off is: richer context → better reasoning quality on bugs Claude does find → but also more abstentions (none) overall.

---

## Output files

| File | Description |
|------|-------------|
| `results/java/results_v4_chart.csv` | v4a results (48 data points, tiers 1-2) |
| `results/java/results_v4b_chart.csv` | v4b results (48 data points, tiers 1-2) |
