# Experiment 9b: Test Flip 

## Method

This reuses the fixes already computed in Experiment 9 and no new Claude calls were made.
For each of the 50 bugs where Experiment 9 applied a fix:

1. **Checkout the buggy version** fresh (`defects4j checkout`)
2. **Run the test suite and capture the *set* of failing test names** (not
   just the count), before the fix
3. **Apply the same fix** Experiment 9 already computed (`original_code` →
   `fixed_code`, already recorded in `results_v9_testfix*.csv`)
4. **Run the test suite again and capture the failing test set**  after the fix
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
| **Any test cases flips to pass** | 11 / 50 | 22.0% |
| — clean pass (all tests now pass) | 8 / 50 | 16.0% |
| — partial (some tests flip to pass, not all) | 3 / 50 | 6.0% |
| Regression only (no flip to pass, but broke previously-passing tests) | 13 / 50 | 26.0% |
| No change (identical failing set before/after) | 26 / 50 | 52.0% |

### By Project

| Category | Chart (21) | Lang (12) | Math (17) |
|---|---|---|---|
| Any flip to pass | 6 (28.6%) | 2 (16.7%) | 3 (17.6%) |
| Clean pass | 5 (23.8%) | 1 (8.3%) | 2 (11.8%) |
| Partial | 1 (4.8%) | 1 (8.3%) | 1 (5.9%) |
| Regression only | 2 (9.5%) | 5 (41.7%) | 6 (35.3%) |
| No change | 13 (61.9%) | 5 (41.7%) | 8 (47.1%) |

The combined clean-pass rate (16.0%) matches Experiment 9's original pass
rate exactly

---

## Output Files

| File | Description |
|---|---|
| `results/java/results_testflip.csv` | All 50 bugs — failing test sets before/after, flip categories |
| `scripts/run/run_experiment_testflip.py` | Test-flip script (reuses Experiment 9 fixes, no new Claude calls) |
| `results/java/results_v9_testfix*.csv` | Source of the fix content re-applied here |

