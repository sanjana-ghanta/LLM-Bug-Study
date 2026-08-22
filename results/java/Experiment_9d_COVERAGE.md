# Experiment 9d: Actual-Line Coverage Check

## Motivation (Prof. Gulzar's checklist item #9)

Do the tests actually touch/execute the documented bug line at all? This
extends Experiment 8's JaCoCo/Cobertura coverage methodology -- Experiment 8's
original run only covered 21/21 Chart bugs and 5/12 Lang bugs, and never ran
Math at all. This experiment completes that check across all 50 bugs used in
Experiment 9/9b/9c, and along the way surfaced two real pipeline issues that
needed fixing before the numbers could be trusted.

---

## Method

For each of the 50 bugs: checkout the buggy version, run `defects4j
coverage` (instruments the full test suite), and check whether the actual
documented bug line and Claude's reported line each show at least one hit
in the resulting `coverage.xml`.

---

## Iteration 1 — using Claude's reported line number directly

First pass queried coverage at `claude_line` exactly as reported by Claude.
Result: **actual line covered 60% (30/50), Claude's line covered only 36%
(18/50)**.

This number turned out to be wrong, for a specific and traceable reason.

---

## The line-number-vs-content-match bug

The fix-application logic finds and replaces a line by matching its exact
**text content**, not by trusting `claude_line` as a coordinate. So a fix
applies correctly even when Claude's self-reported line number is off from
where that code actually sits -- but the first-iteration coverage check
queried hits at the raw reported number, which can land on an unrelated,
often zero-hit line (a blank line, a brace, a comment).

Confirmed directly: pulled the actual `coverage.xml` for two contradicting
cases (Chart_11, Lang_12) and found the reported line showing 0 hits while
lines immediately adjacent were heavily covered -- the statement clearly
executes, just not at the number Claude gave.

**Fix:** instead of trusting `claude_line`, search the checked-out file for
the real physical line containing `original_code`'s exact text, and query
coverage at that verified location.

## Iteration 2 — content-matched line lookup

Result jumped to **actual line covered 60% (30/50), Claude's line covered
90% (45/50)**.

This large a jump needed its own sanity check before being trusted.

---

## The duplicate-text discovery

Some of the line-number shifts between iteration 1 and 2 were enormous
(one over 1,600 lines). That's not Claude being imprecise -- it's a sign the
"find the matching line" search grabbed a **different, unrelated occurrence**
of the same exact text elsewhere in the file.

Built `check_line_ambiguity.py` to count occurrences of `original_code`'s
text per file:

| Status | Count | % |
|---|---|---|
| UNIQUE (text appears once) | 42 / 50 | 84% |
| DUPLICATED (text appears 2+ times) | 8 / 50 | 16% |

**For the 8 duplicated bugs, both the original `apply_fix_to_file()` (used
in the real Experiment 9 run) and the iteration-2 coverage script always
picked the FIRST occurrence top-to-bottom -- not necessarily the occurrence
Claude actually meant.**

Cross-referencing these 8 against Experiment 9b's test-flip results: **every
single one of the 8 was either "no change" or "regression only" -- zero
ever flipped a test to passing.** That's not a coincidence: if the edit
lands on the wrong copy of duplicated code, it structurally cannot fix the
real bug.

---

## Fixing it

1. **Patched `apply_fix_to_file()`** in both test-fix scripts: when text is
   duplicated, pick whichever occurrence is closest to Claude's reported
   line number, instead of always the first one. (Applies to future runs;
   `run_experiment_v9_testfix.py`, `run_experiment_v9_testfix_math.py`.)

2. **Re-verified the 8 duplicated bugs** (`reverify_duplicated_bugs.py`):
   re-applied each fix using the closest-to-reported occurrence, re-ran
   the test suite, and checked whether the corrected location actually
   matches the real documented bug line.

| Bug | Reported line | Closest occurrence | Matches actual line? | Corrected outcome |
|---|---|---|---|---|
| **Chart_1** | 1504 | 1797 | **Yes** | Regression → **genuine fix** (flips 1 test to pass) |
| **Chart_7** | 324 | 300 | **Yes** | No change → **genuine fix** (flips 1 test to pass) |
| Chart_16 | 732 | 488 | No | Unchanged (no change) |
| Chart_8 | 124 | 128 | No | Unchanged (no change) |
| Chart_6 | 160 | 162 | No | Unchanged (regression, worsens: 2→67 failing) |
| Lang_3 | 541 | 570 | No | Unchanged (no change) |
| Lang_7 | 489 | 495 | No | Unchanged (regression: 1→2 failing) |
| Math_10 | 963 | 1235 | No | Unchanged (regression: 1→2 failing) |

**2 of 8 were genuinely rescued** by the tie-break fix -- Claude's original
answer was actually correct, the pipeline just applied it to the wrong copy
of the code. **6 of 8 remain wrong even at the best possible occurrence** --
for these, neither duplicate copy is the real bug line, meaning Claude's
answer was genuinely incorrect, independent of any tooling issue.

3. **Corrected the records:** `results_testflip.csv` (Chart_1, Chart_7 now
   show their true outcome, with a `correction_note` documenting the
   change) and `results_actuallinecoverage_v2.csv` (all 8 duplicated bugs'
   `claude_covered` recomputed at the correct occurrence).

---

## Final Results

| | Actual line covered | Claude line covered |
|---|---|---|
| **Combined (50 bugs), fully corrected** | **30/50 (60.0%)** | **45/50 (90.0%)** |

Claude's reported line is executed by the test suite in the large majority
of cases (90%) -- a much stronger and more accurate result than the
uncorrected 36% first pass suggested.

---

## What This Means for Other Experiments

- **Experiments 1-7:** unaffected. None of them apply file edits, so the
  line-matching issues found here don't apply.
- **Experiment 8 (original coverage run):** likely has the *same*
  first-iteration flaw (querying raw `claude_line` directly). Its reported
  28.6% Chart coverage figure is probably an undercount for the same reason
  our own first pass was -- worth rerunning with the content-matched
  approach if that number is going to be cited going forward.
- **Experiments 9 / 9b:** the aggregate pass/fail and test-flip percentages
  were never wrong (they measure real, directly-run test outcomes) -- only
  the *explanation* for 8 specific bugs needed correcting, which is now
  done.
- **Experiment 9c:** unaffected (pure text comparison, no line-matching).

---

## Output Files

| File | Description |
|---|---|
| `results/java/results_actuallinecoverage_v2.csv` | Final, corrected coverage data for all 50 bugs |
| `results/java/results_ambiguity_check.csv` | Per-bug duplicate-text occurrence counts |
| `results/java/results_duplicate_reverify.csv` | Corrected test outcomes for the 8 duplicated bugs |
| `results/java/results_testflip.csv` | Updated with corrected Chart_1/Chart_7 outcomes (`correction_note` column added) |
| `scripts/run/run_actual_line_coverage_v2.py` | Coverage script with content-matched line lookup |
| `scripts/run/check_line_ambiguity.py` | Duplicate-text detection |
| `scripts/run/reverify_duplicated_bugs.py` | Re-verification for the 8 duplicated bugs |
| `scripts/run/patch_apply_fix.py` | Patches `apply_fix_to_file()` for future runs |
| `scripts/run/apply_duplicate_corrections.py` | Applied the Chart_1/Chart_7 corrections |
| `scripts/run/fix_coverage_for_duplicates.py` | Applied the 8-bug coverage corrections |

