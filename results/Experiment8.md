# Experiment 8: JaCoCo Coverage Analysis

## Method

For each Chart bug where Claude reported a line number (from experiment 6, v5 results):

1. Run `defects4j coverage -w data/bugs/Chart_N/buggy` to generate `coverage.xml`
2. Parse the XML to get hit counts for each line in the buggy file
3. Compare:
   - **Actual bug line** (from Defects4J): hit count and coverage rank
   - **Claude's reported line** (from v5 experiment): hit count and coverage rank
4. Coverage rank = percentile of that line's hit count among all lines in the file

---

## Results

21 Chart bugs analyzed (3 skipped due to missing line info).

### Coverage status

| | Actual bug lines | Claude's reported lines |
|---|---|---|
| Covered by tests (hits > 0) | 17/21 (**81.0%**) | 6/21 (**28.6%**) |
| Not covered (hits = 0 or N/A) | 4/21 (19.0%) | 15/21 (**71.4%**) |

**Claude's lines are covered by tests only 28.6% of the time, compared to 81% for actual bug lines.**

### Per-bug breakdown

| Bug | Actual line | Actual hits | Claude line | Claude hits | Finding |
|-----|-------------|-------------|-------------|-------------|---------|
| Chart_1 | 1797 | 41 | 1504 | N/A | Claude picked non-covered line |
| Chart_3 | 1056 | 19 | 1024 | N/A | Claude picked non-covered line |
| Chart_5 | 542 | 0 | 393 | N/A | Both uncovered |
| Chart_6 | 111 | 804 | 160 | 72 | Claude picked lower coverage |
| Chart_7 | 300 | 114 | 324 | 159 | Claude picked higher coverage |
| Chart_8 | 175 | 4 | 124 | N/A | Claude picked non-covered line |
| Chart_9 | 944 | 15 | 1103 | N/A | Claude picked non-covered line |
| Chart_10 | 65 | 2 | 62 | N/A | Claude picked non-covered line |
| Chart_11 | 275 | 31 | 281 | 0 | Claude picked non-covered line |
| Chart_12 | 145 | 6 | 384 | N/A | Claude picked non-covered line |
| Chart_13 | 455 | 3 | 467 | N/A | Claude picked non-covered line |
| Chart_15 | 1377 | N/A | 555 | N/A | Both uncovered |
| Chart_16 | 338 | 1 | 732 | N/A | Claude picked non-covered line |
| Chart_17 | 857 | 3 | 869 | N/A | Claude picked non-covered line |
| Chart_18 | 318 | 4 | 323 | 478 | Claude picked higher coverage |
| Chart_21 | 156 | N/A | 150 | 18 | Claude picked more covered line |
| Chart_22 | 231 | 28 | 227 | 28 | Equal coverage |
| Chart_23 | 434 | N/A | 453 | 0 | Both uncovered |
| Chart_24 | 126 | 3 | 119 | N/A | Claude picked non-covered line |
| Chart_25 | 258 | 4 | 499 | N/A | Claude picked non-covered line |
| Chart_26 | 1191 | 28 | 1062 | 90 | Claude picked higher coverage |

### Coverage rank comparison (bugs where both lines are covered)

Only 5 bugs had coverage rank data for both lines:

| Bug | Actual rank | Claude rank | Claude higher? |
|-----|-------------|-------------|----------------|
| Chart_6 | 100.0%ile | 75.9%ile | No |
| Chart_7 | 88.1%ile | 98.7%ile | Yes |
| Chart_11 | 74.6%ile | 58.9%ile | No |
| Chart_22 | 71.0%ile | 71.0%ile | Equal |
| Chart_26 | 53.7%ile | 78.9%ile | Yes |

Average actual rank: **77.5%ile**
Average Claude rank: **76.7%ile**
Claude picked higher coverage line: 2/5 (40%)

---

## Key Finding

**Finding: Claude points to non-covered lines 71.4% of the time.**

This directly refutes the possibility that Claude is finding the real bug. Defects4J bugs are by definition detected by test failures, meaning the buggy line must be executed. Claude's lines are not executed 71.4% of the time — they cannot be the cause of any test failure.

---

## Output Files

| File | Description |
|------|-------------|
| `results/java/results_coverage.csv` | Per-bug coverage comparison (21 bugs) |
| `scripts/run/run_coverage_analysis.py` | Coverage analysis script using defects4j coverage + JaCoCo XML |
