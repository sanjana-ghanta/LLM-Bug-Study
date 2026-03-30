# LLM Bug Detection Study

A systematic empirical study evaluating Claude's ability to detect bugs in real Java code across 5 experimental tiers, using 45 bugs from the Defects4J benchmark.

## Research Question

How robust is LLM-based bug detection to different code transformations — including the original bug, semantic-preserving mutations (SPMs), and surface-level rewrites?

## Dataset

48 real bugs from [Defects4J](https://github.com/rjust/defects4j) across 3 projects:

| Project | Bugs | Description |
|---------|------|-------------|
| Apache Commons Lang | 18 | String/number utilities |
| Apache Commons Math | 20 | Math library |
| JFreeChart | 10 | Charting library |

45 bugs have all 5 tiers complete (3 bugs had no eligible SPM mutation sites).

## Experimental Design

Each bug is tested across 5 tiers:

| Tier | Code Presented to LLM | Correct Answer |
|------|----------------------|----------------|
| 1 | Patched (clean) code | NO BUG |
| 2 | Original buggy code | BUG |
| 3 | Patched code + SPM injected bug | BUG |
| 4 | Original buggy code + SPM injected bug | BUG |
| 5 | Semantically rewritten buggy code | BUG |

**SPM types used:** off-by-one (`<` ↔ `<=`), operator swap (`+` ↔ `-`), boolean logic (`&&` ↔ `||`)

**Prompt used (no prompt engineering):**
```
Review the following Java code from {file} and determine if it contains a bug.
Respond in this exact format:
VERDICT: BUG or NO BUG
REASON: <one sentence explanation>
```

## Results

| Tier | Description | Correct | Total | Accuracy |
|------|-------------|---------|-------|----------|
| 1 | Patched code | 50 | 60 | 83.3% |
| 2 | Original buggy | 13 | 60 | 21.7% |
| 3 | Patched + SPM | 11 | 55 | 20.0% |
| 4 | Original + SPM | 8 | 55 | 14.5% |
| 5 | Semantic rewrite | 11 | 60 | 18.3% |

**False positive rate (tier 1):** 16.7% — Claude incorrectly flags clean code as buggy  
**False negative rate (tiers 2-5):** 81.3% — Claude misses real bugs 4 out of 5 times

### By Project

| Project | Correct | Total | Accuracy |
|---------|---------|-------|----------|
| Chart | 24 | 50 | 48.0% |
| Lang | 26 | 88 | 29.5% |
| Math | 43 | 152 | 28.3% |

## Key Findings

- Claude is much better at recognizing clean code (83%) than detecting bugs (14-22%)
- Bug detection accuracy drops as code complexity increases (tier 4 is worst at 14.5%)
- Surface-level rewrites of buggy code are hard for Claude to detect (18.3% on tier 5)
- Claude's bug detection is not robust to semantic-preserving transformations

## Repository Structure
```
experiment/
├── extract_bug.py          # Extracts changed files from Defects4J checkouts
├── recheckout_all.py       # Checks out all 48 bugs from Defects4J
├── inject_spm.py           # Injects semantic-preserving mutations (tiers 3 & 4)
├── generate_tier5.py       # Generates semantic rewrites via Claude API (tier 5)
├── run_experiment.py       # Main experiment runner — sends all tiers to Claude
├── results.csv             # Full results (290 data points)
└── bugs/                   # Per-bug data.json files (not tracked in git)
```

## Setup & Replication

### Prerequisites
- Python 3.9+
- [Defects4J v3](https://github.com/rjust/defects4j) installed and on PATH
- Anthropic API key

### Steps
```bash
# 1. Clone this repo
git clone https://github.com/sanjana-ghanta/LLM-Bug-Study.git
cd LLM-Bug-Study

# 2. Install dependencies
pip install anthropic

# 3. Set your API key
export ANTHROPIC_API_KEY="your-key-here"

# 4. Checkout all bugs from Defects4J
python3 recheckout_all.py

# 5. Inject SPM mutations (tiers 3 & 4)
python3 inject_spm.py

# 6. Generate semantic rewrites (tier 5)
python3 generate_tier5.py

# 7. Run the experiment
python3 run_experiment.py

# Results saved to results.csv
```

## Model Used

Claude Sonnet (`claude-sonnet-4-20250514`) via the Anthropic API

## Acknowledgements

- [Defects4J](https://github.com/rjust/defects4j) benchmark by René Just et al.
- [LLM-Debug](https://github.com/sabaat/LLM-Debug) repo for SPM injection inspiration
- Research conducted under the guidance of Prof. Mohammed Ali Gulzar, Virginia Tech
