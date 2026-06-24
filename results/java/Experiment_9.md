# Experiment 9: Test Fix Experiment

## Motivation
Experiment 9 asks a different question: **even if Claude points to the wrong line, can it suggest a fix that actually works?**

This separates two things that previous experiments conflated:
1. **Location accuracy** — did Claude find the right line?
2. **Reasoning quality** — does Claude understand what's wrong and how to fix it?

It's possible that Claude understands the type of bug and the correct fix, but simply can't locate the specific documented instance. If Claude's fix passes the test suite even at a different line, that's evidence of genuine (even if imprecise) reasoning.

---

## Method

For each bug where Claude reported a line number (from v5-style experiments):

1. **Checkout the buggy version** using `defects4j checkout`
2. **Count failing tests before the fix** using `defects4j test`
3. **Ask Claude to suggest a fix** at its reported line:
   ```
   You previously identified a bug on line {claude_line}.
   The bug is related to {hint}.

   ORIGINAL: <exact current line>
   FIXED: <corrected line>
   EXPLANATION: <one sentence>
   ```
4. **Apply the fix** to the checked-out source file — replace the original line with the fixed line, preserving indentation
5. **Count failing tests after the fix** using `defects4j test`
6. **Record:** fix applied, tests before, tests after, improvement, passed

The fix is applied to a temporary `/tmp/` directory and deleted after each bug — no permanent changes to source files.

Run on:
- **Chart:** 21 bugs (from results_v5_chart.csv)
- **Lang:** 41 bugs (from results_v5_lang.csv)
- **Math:** 17 bugs (from results_v5_math.csv)

---

## Results

### By Project

| Metric | Chart (21) | Lang (12) | Math (17) |
|--------|-----------|-----------|-----------|
| Fix applied | 21/21 (100%) | 12/12 (100%) | 17/17 (100%) |
| Tests passed | **4/21 (19.0%)** | **1/12 (8.3%)** | **3/17 (17.6%)** |
| Partial improvement | 6/21 (28.6%) | 1/12 (8.3%) | 3/17 (17.6%) |
| No change | 13/21 (61.9%) | 4/12 (33.3%) | 8/17 (47.1%) |
| Made it worse | 2/21 (9.5%) | 6/12 (50.0%) | 6/17 (35.3%) |

### Combined (50 bugs)

| Metric | Result |
|--------|--------|
| Fixes successfully applied | 50/50 (100.0%) |
| Tests passed | **8/50 (16.0%)** |
| Partial improvement | 10/50 (20.0%) |
| Made it worse | **14/50 (28.0%)** |

**Claude is more likely to break working code (28%) than to fix broken code (16%).**

---

## All Passing Fixes

| Bug | Claude line | Actual line | Diff | Fix |
|-----|-------------|-------------|------|-----|
| Chart_10 | 62 | 65 | 3 | `toolTipText` → `toolTipText.replace("\"", "&quot;")` |
| Chart_11 | 281 | 275 | 6 | `p1.getPathIterator(null)` → `p2.getPathIterator(null)` |
| Chart_21 | 150 | 156 | 6 | `minval < minimumRangeValue` → `!Double.is...` |
| Chart_24 | 119 | 126 | 7 | `value - lowerBound` → `v - lowerBound` |
| Lang_6 | 88 | 95 | 7 | `pt < consumed` → `pt < consumed && pos < len` |
| Math_6 | 195 | 51 | 144 | `if (data instanceof MaxIter)` → `} else if (data instanceof MaxIter)` |
| Math_11 | 175 | 183 | 8 | `-dim / 2)` → `-dim / 2.0)` |
| Math_16 | 2044 | 81 | 1963 | Added bounds clamp `if (idx > 13) idx = 13;` |

Most passing fixes are 3-8 lines from the documented bug. Math_6 (diff=144) and Math_16 (diff=1963) are outliers — Claude fixed a real bug in the same file that wasn't the officially documented one.

---

## Notable Cases

### Chart_10 — Correct fix, 3 lines off
Claude added HTML quote escaping to a tooltip string: `.replace("\"", "&quot;")`. This is a real HTML injection bug and the fix is correct. Same method, Claude pointed to the start of the method rather than the specific return statement.

### Chart_8 — Right fix, wrong constructor (diff=51, no pass)
Claude correctly identified `&&` should be `||` in week range validation — `week < 1 AND week > 53` is logically impossible so the check never fires. Fix is logically sound. But the same pattern appears in two constructors and Claude fixed the wrong one. Tests still fail because the documented bug is in the other constructor.

### Math_11 — Integer division fix (diff=8)
Claude identified `-dim / 2` should be `-dim / 2.0` to avoid integer division truncation. This is a real arithmetic bug and the fix passes all tests. 8 lines from the documented location, same method.

### Math_6 — Largest passing diff (diff=144)
Claude changed `if (data instanceof MaxIter)` to `} else if (data instanceof MaxIter)`, fixing a control flow issue where the MaxIter branch could never be reached. This is a genuine bug in the codebase — just not the officially documented one. The fix passes tests.

### Math_13 — Catastrophic (1 → 37 failing)
Claude changed `getChiSquare() / rows` to `getChiSquare() / (rows - cols)`, arguing this is the correct degrees-of-freedom formula. The formula looks statistically plausible but is wrong in this context — it cascaded across 37 tests.

### Lang_9 and Lang_10 — Catastrophic (2 → 33 failing)
Claude "fixed" `for(int i=0; i<strategies.length;)` by adding `++i`. This is an intentional self-controlled loop with internal break logic. Adding a standard increment completely broke the parsing strategy.

### Chart_1 — Made dramatically worse (1 → 9 failing)
Claude flipped `if (dataset != null)` to `if (dataset == null)`. Correct reasoning — inverted null check. But applied to the wrong null check (line 1504 vs actual 1797), which is a different conditional controlling a different code path.

---

## All "Made Worse" Cases

| Bug | Before | After | Fix attempted |
|-----|--------|-------|---------------|
| Chart_5 | 1 | 2 | Removed `allowDuplicateXValues` check |
| Chart_1 | 1 | 9 | Flipped null check at wrong line |
| Lang_3 | 1 | 2 | Changed `str.length() - 1` → `str.length()` |
| Lang_5 | 1 | 2 | Changed substring index 6 → 5 |
| Lang_7 | 1 | 2 | Same as Lang_3 — identical pattern match |
| Lang_9 | 2 | 33 | Added `++i` to intentional infinite loop |
| Lang_10 | 2 | 33 | Same as Lang_9 — identical bug in same file |
| Lang_12 | 2 | 3 | Changed `end - start` → `end - start + 1` |
| Math_3 | 1 | 2 | Changed `xLen` → `hLen` in wrong place |
| Math_4 | 2 | 4 | Changed `==` to `!=` in location check |
| Math_5 | 1 | 5 | Changed `k < n` to `k <= n` (off-by-one wrong direction) |
| Math_10 | 1 | 2 | Changed `k -= 2` to `--k` breaking step logic |
| Math_13 | 1 | 37 | Wrong degrees-of-freedom formula |
| Math_17 | 1 | 2 | Off-by-one in wrong direction |

---

## Key Findings

**Project complexity determines "made worse" rate.**

| Project | Pass rate | Made worse |
|---------|-----------|------------|
| Chart | 19.0% | 9.5% |
| Math | 17.6% | 35.3% |
| Lang | 8.3% | 50.0% |

Lang and Math bugs involve complex algorithmic logic (string parsing, numerical methods) where wrong fixes cascade across many tests. Chart bugs are more isolated rendering methods.

**All evidence from experiments 6-9 converges.**

- Exp 6: 87.5% pattern match rate on clean code
- Exp 7: Self-describes as "confabulating" 10/10
- Exp 8: 71.4% of Claude's lines not covered by tests
- Exp 9: 16% pass rate, always at wrong line, 28% made worse

---

## Comparison Across Projects

| Project | Files | Avg file size | Pass rate | Made worse |
|---------|-------|--------------|-----------|------------|
| Chart | Rendering classes | Medium | 19.0% | 9.5% |
| Math | Numerical algorithms | Medium-large | 17.6% | 35.3% |
| Lang | String utilities | Large (StringUtils 6000+ lines) | 8.3% | 50.0% |

The pattern is clear in that larger files with more complex logic and denser test coverage have a lower pass rate and higher "made worse" rate. Claude's pattern matching approach works better on smaller, more isolated classes.

---

## Output Files

| File | Description |
|------|-------------|
| `results/java/results_v9_testfix.csv` | Chart 21 bugs |
| `results/java/results_v9_testfix_lang.csv` | Lang 41 bugs |
| `results/java/results_v9_testfix_math.csv` | Math 17 bugs |
| `scripts/run/run_experiment_v9_testfix.py` | Chart + Lang script |
| `scripts/run/run_experiment_v9_testfix_math.py` | Math script |
| `scripts/run/run_experiment_v5_lang.py` | v5 line recall for Lang |
| `scripts/run/run_experiment_v5_math.py` | v5 line recall for Math |
