# Experiment 9b: Test-Flip Attribution

## Motivation

Experiment 9 measured whether Claude's proposed fix makes the full test suite
pass (16.0%) or fail worse (28.0%). But "pass/fail" and even failing-test
*counts* can hide what's actually happening. A count that looks unchanged
(e.g. 1 → 1 failing) can silently hide a real effect: one test flips to
passing while a *different* test breaks, netting to the same number.

Per Prof. Gulzar's framing: the test suite is the only ground truth we have
for whether a line is actually buggy. So the real question isn't "did the
count go down" — it's **did fixing Claude's line flip any specific test from
failing to passing?** If yes, that's direct evidence Claude's line is
verifiably buggy, by the only oracle available, regardless of whether it
matches the officially documented line.

---

## Method

This reuses the fixes already computed in Experiment 9 — no new Claude calls.
For each of the 50 bugs where Experiment 9 applied a fix:

1. **Checkout the buggy version** fresh (`defects4j checkout`)
2. **Run the test suite and capture the *set* of failing test names** (not
   just the count) — before the fix
3. **Apply the same fix** Experiment 9 already computed (`original_code` →
   `fixed_code`, already recorded in `results_v9_testfix*.csv`)
4. **Run the test suite again and capture the failing test set** — after the fix
5. **Compute the set difference:**
   - `flipped_to_pass` = failed before, passes now
   - `flipped_to_fail` = passed before, fails now (a regression)
   - `still_failing` = failed both times, unaffected by the fix

Run on the same 50 bugs as Experiment 9: Chart (21), Lang (12), Math (17).

---

## Results

### Combined (50 bugs)

| Category | Count | % |
|---|---|---|
| **Any flip to pass** (Claude's line verified buggy by ≥1 test) | 11 / 50 | 22.0% |
| — clean pass (all tests now pass) | 8 / 50 | 16.0% |
| — partial (some tests flip to pass, not all) | 3 / 50 | 6.0% |
| Regression only (no flip to pass, but broke previously-passing tests) | 13 / 50 | 26.0% |
| No change (identical failing set before/after) | 26 / 50 | 52.0% |

### By Project

| Metric | Chart (21) | Lang (12) | Math (17) |
|---|---|---|---|
| Any flip to pass | 6 (28.6%) | 2 (16.7%) | 3 (17.6%) |
| Clean pass | 5 (23.8%) | 1 (8.3%) | 2 (11.8%) |
| Partial | 1 (4.8%) | 1 (8.3%) | 1 (5.9%) |
| Regression only | 2 (9.5%) | 5 (41.7%) | 6 (35.3%) |
| No change | 13 (61.9%) | 5 (41.7%) | 8 (47.1%) |

**The combined clean-pass rate (16.0%) matches Experiment 9's original pass
rate exactly** — same underlying reality, confirmed by a completely
independent test-name-level recomputation. That agreement is a useful sanity
check on the new script, separate from the two per-bug discrepancies noted
below.

---

## The Cases That Motivated This Redesign

Two bugs would have been mischaracterized by count alone:

### Math_2 — hidden mixed signal
`n_before=1, n_after=1`. Identical count — a count-only view logs this as
"no improvement." But the actual test *sets* differ: the originally-failing
test flipped to pass, and a different test broke in its place. Claude's line
is genuinely implicated in the original bug, but the fix also introduces a
new problem.

### Lang_12 — regression outweighing a real fix
`n_before=2, n_after=3`. Looks like a small regression by count. Actually: 1
test flipped to pass (a real fix), 2 different tests flipped to fail. Mixed
signal, invisible without test identity.

These are the only two bugs in the full set of 50 with **both**
`flipped_to_pass > 0` and `flipped_to_fail > 0` — i.e., the only bugs where
Claude's edit is simultaneously a real (partial) fix and a regression.
Everything else splits cleanly into "helped," "hurt," or "did nothing."

---

## Correction to Experiment 9's Original Write-Up

Cross-checking this run against Experiment 9's original "All Passing Fixes"
table surfaced a discrepancy on two bugs, which was investigated with
repeated determinism checks (5x baseline, no fix; then 5x with the fix
applied, same checkout reused across runs — see
`scripts/run/check_flakiness.py` and `check_flakiness_after_fix.py`).
**Both bugs were fully deterministic in every run** — this is not test
flakiness. The findings:

| Bug | Experiment 9 (original) | Verified (10/10 identical runs) | Conclusion |
|---|---|---|---|
| **Chart_26** | Not listed as passing | Clean pass every time (22 → 0 failing) | **Genuinely passes.** Experiment 9's original run appears to have hit a one-off environment issue (not the fix's fault) and simply mischaracterized this one bug. |
| **Math_16** | Listed as passing (diff=1963, bounds-clamp fix) | No change every time — the same two tests (`FastMathTest::testMath905LargeNegative`, `testMath905LargePositive`) fail identically before and after the fix | **Does not actually pass.** Experiment 9's original write-up is incorrect for this bug — the fix has zero measurable effect on the test suite. |

**Action needed:** `results/java/Experiment_9.md`'s "All Passing Fixes" table
and pass-rate figures should be corrected — Math_16 should be removed from
the passing list and Chart_26 added. The combined 16.0% clean-pass rate
happens to stay the same either way (one swapped for the other), but the
per-project Chart/Math breakdown in that document is off by one bug in each
direction and should be updated to match `results_testflip.csv`, which is
the verified source of truth going forward.

---

## Output Files

| File | Description |
|---|---|
| `results/java/results_testflip.csv` | All 50 bugs — failing test sets before/after, flip categories |
| `scripts/run/run_experiment_testflip.py` | Test-flip script (reuses Experiment 9 fixes, no new Claude calls) |
| `results/java/results_v9_testfix*.csv` | Source of the fix content re-applied here |

