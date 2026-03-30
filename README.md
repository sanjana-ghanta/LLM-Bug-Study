# LLM Bug Detection Study

A systematic empirical study evaluating LLM ability to detect bugs in real Java and Python code across 5 experimental tiers, using 45 Java bugs from Defects4J and 50 Python bugs from BugsInPy.

## Research Question

How robust is LLM-based bug detection to different code transformations — including the original bug, semantic-preserving mutations (SPMs), and surface-level rewrites? Does this differ between Java and Python?

## Dataset

### Java — Defects4J
45 bugs (all 5 tiers complete) from 3 projects:

| Project | Bugs | Description |
|---------|------|-------------|
| Apache Commons Lang | 18 | String/number utilities |
| Apache Commons Math | 20 | Math library |
| JFreeChart | 10 | Charting library |

### Python — BugsInPy
50 bugs from 3 projects:

| Project | Bugs | Description |
|---------|------|-------------|
| pandas | 25 | Data analysis library |
| black | 15 | Code formatter |
| thefuck | 10 | Shell command corrector |

## Experimental Design

Each bug is tested across 5 tiers:

| Tier | Code Presented to LLM | Correct Answer |
|------|----------------------|----------------|
| 1 | Patched (clean) code | NO BUG |
| 2 | Original buggy code | BUG |
| 3 | Patched code + SPM injected bug | BUG |
| 4 | Original buggy code + SPM injected bug | BUG |
| 5 | Semantically rewritten buggy code | BUG |

**SPM types used:** off-by-one (`<` ↔ `<=`), operator swap (`+` ↔ `-`), boolean logic (`&&` ↔ `||` for Java, `and` ↔ `or` for Python)

**Prompt used (no prompt engineering):**
```
Review the following code from {file} and determine if it contains a bug.
Respond in this exact format:
VERDICT: BUG or NO BUG
REASON: <one sentence explanation>
```

## Results

### Java (Claude Sonnet)

| Tier | Description | Correct | Total | Accuracy |
|------|-------------|---------|-------|----------|
| 1 | Patched code | 50 | 60 | 83.3% |
| 2 | Original buggy | 13 | 60 | 21.7% |
| 3 | Patched + SPM | 11 | 55 | 20.0% |
| 4 | Original + SPM | 8 | 55 | 14.5% |
| 5 | Semantic rewrite | 11 | 60 | 18.3% |

**False positive rate:** 16.7% | **False negative rate:** 81.3%

#### By Project (Java)
| Project | Correct | Total | Accuracy |
|---------|---------|-------|----------|
| Chart | 24 | 50 | 48.0% |
| Lang | 26 | 88 | 29.5% |
| Math | 43 | 152 | 28.3% |

---

### Python (Claude Haiku)

| Tier | Description | Correct | Total | Accuracy |
|------|-------------|---------|-------|----------|
| 1 | Patched code | 41 | 50 | 82.0% |
| 2 | Original buggy | 9 | 50 | 18.0% |
| 3 | Patched + SPM | 6 | 45 | 13.3% |
| 4 | Original + SPM | 6 | 44 | 13.6% |
| 5 | Semantic rewrite | 2 | 26 | 7.7% |

**False positive rate:** 18.0% | **False negative rate:** 86.1%

#### By Project (Python)
| Project | Correct | Total | Accuracy |
|---------|---------|-------|----------|
| black | 15 | 75 | 20.0% |
| pandas | 30 | 111 | 27.0% |
| thefuck | 19 | 29 | 65.5% |

---

### Java vs Python Comparison

| Tier | Java (Sonnet) | Python (Haiku) |
|------|--------------|----------------|
| 1 (clean code) | 83.3% | 82.0% |
| 2 (original bug) | 21.7% | 18.0% |
| 3 (patched + SPM) | 20.0% | 13.3% |
| 4 (original + SPM) | 14.5% | 13.6% |
| 5 (semantic rewrite) | 18.3% | 7.7% |
| False positive rate | 16.7% | 18.0% |
| False negative rate | 81.3% | 86.1% |

> **Note:** Java used Claude Sonnet and Python used Claude Haiku. Some differences may reflect model capability rather than language difficulty.

## Key Findings

- LLMs are much better at recognizing clean code (~83%) than detecting real bugs (~18-22%)
- Bug detection accuracy drops as code complexity increases (tier 4 worst at 13-14%)
- Semantic rewrites fool the model significantly, especially in Python (7.7%)
- False negative rate is very high across both languages (81-86%)
- thefuck bugs are easiest to detect (65.5%) — likely due to small, focused file sizes
- black bugs are hardest (20%) — complex code formatter logic

## Repository Structure
```
experiment/
├── extract_bug.py              # Extracts changed Java files from Defects4J
├── extract_pybug.py            # Extracts changed Python files from BugsInPy
├── recheckout_all.py           # Checks out all 48 Java bugs from Defects4J
├── extract_all_pybugs.py       # Extracts all 50 Python bugs from BugsInPy
├── inject_spm.py               # Injects SPMs into Java code (tiers 3 & 4)
├── inject_spm_python.py        # Injects SPMs into Python code (tiers 3 & 4)
├── generate_tier5.py           # Generates Java semantic rewrites via Claude (tier 5)
├── generate_tier5_python.py    # Generates Python semantic rewrites via Claude (tier 5)
├── run_experiment.py           # Main Java experiment runner
├── run_experiment_python.py    # Main Python experiment runner
├── results.csv                 # Java results (290 data points)
├── results_python.csv          # Python results (215 data points)
└── bugs/                       # Per-bug data.json files — Java (not tracked)
└── pybugs/                     # Per-bug data.json files — Python (not tracked)
```

## Setup & Replication

### Prerequisites
- Python 3.9+
- [Defects4J v3](https://github.com/rjust/defects4j) installed and on PATH
- [BugsInPy](https://github.com/soarsmu/BugsInPy) installed and on PATH
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

# 4. Java experiment
python3 recheckout_all.py
python3 inject_spm.py
python3 generate_tier5.py
python3 run_experiment.py

# 5. Python experiment
python3 extract_all_pybugs.py
python3 inject_spm_python.py
python3 generate_tier5_python.py
python3 run_experiment_python.py
```

## Models Used

- Java experiment: Claude Sonnet (`claude-sonnet-4-20250514`)
- Python experiment: Claude Haiku (`claude-haiku-4-5-20251001`)

## Acknowledgements

- [Defects4J](https://github.com/rjust/defects4j) benchmark by René Just et al.
- [BugsInPy](https://github.com/soarsmu/BugsInPy) benchmark
- [LLM-Debug](https://github.com/sabaat/LLM-Debug) repo for SPM injection inspiration
- Research conducted under the guidance of Prof. Mohammed Ali Gulzar, Virginia Tech
