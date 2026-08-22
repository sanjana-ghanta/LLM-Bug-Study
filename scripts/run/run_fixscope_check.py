"""
Experiment 9c: Fix Scope Check

Question: does Claude's fix change just the one line, or something bigger?

Important mechanical note: apply_fix_to_file() in the Experiment 9 pipeline
only ever replaces a SINGLE matched line in the file -- it structurally
cannot touch other lines or files. So "does Claude change the whole
project" can't literally happen under this pipeline. The real, answerable
version of the question is: does the CONTENT of that one replaced line
represent a minimal, single-statement fix (e.g. one value or operator
changed), or does Claude smuggle in extra statements/logic compressed onto
that same line (e.g. Math_16: original was one assignment, fixed_code added
a whole new "if (idx > 13) idx = 13;" statement chained on with a semicolon)?

This reuses results_v9_testfix*.csv -- no new Claude calls, no reruns.
"""

import csv
import os
import re

BASE = os.path.expanduser("~/llm-bug-study/experiment")
OUT_CSV = os.path.join(BASE, "results/java/results_fixscope.csv")

SOURCES = [
    ("Chart", os.path.join(BASE, "results/java/results_v9_testfix.csv")),
    ("Lang", os.path.join(BASE, "results/java/results_v9_testfix_lang.csv")),
    ("Math", os.path.join(BASE, "results/java/results_v9_testfix_math.csv")),
]


def count_statements(code):
    """Rough statement count: split on ';' that aren't inside a for(...) loop header."""
    # ignore semicolons inside for(...) since those are loop headers, not separate statements
    code_no_for_headers = re.sub(r'for\s*\([^)]*\)', 'FORLOOP', code)
    parts = [p.strip() for p in code_no_for_headers.split(';') if p.strip()]
    return len(parts)


def classify(original, fixed):
    orig_stmts = count_statements(original)
    fixed_stmts = count_statements(fixed)
    stmt_delta = fixed_stmts - orig_stmts

    orig_len = len(original.strip())
    fixed_len = len(fixed.strip())
    len_ratio = fixed_len / orig_len if orig_len > 0 else float('inf')

    if stmt_delta <= 0 and len_ratio <= 1.5:
        category = "minimal_edit"          # same or fewer statements, modest length change
    elif stmt_delta >= 1:
        category = "added_statement(s)"    # smuggled extra logic onto the line
    elif len_ratio > 1.5:
        category = "large_rewrite"         # ballooned in size without adding full statements
    else:
        category = "other"

    return orig_stmts, fixed_stmts, stmt_delta, round(len_ratio, 2), category


rows_out = []
for project, path in SOURCES:
    if not os.path.exists(path):
        print(f"Skipping {project}: {path} not found")
        continue
    with open(path) as f:
        rows = list(csv.DictReader(f))

    print(f"\n=== {project}: {len(rows)} bugs ===")
    for row in rows:
        if row.get('fix_applied', 'False') != 'True':
            continue
        original = row.get('original_code', '')
        fixed = row.get('fixed_code', '')
        if not original or not fixed:
            continue

        orig_stmts, fixed_stmts, stmt_delta, len_ratio, category = classify(original, fixed)

        print(f"  {project}_{row['bug_id']}: {orig_stmts} -> {fixed_stmts} statements "
              f"(delta {stmt_delta:+d}), length ratio {len_ratio}x -> {category}")

        rows_out.append({
            'project': project,
            'bug_id': row['bug_id'],
            'orig_statements': orig_stmts,
            'fixed_statements': fixed_stmts,
            'statement_delta': stmt_delta,
            'length_ratio': len_ratio,
            'category': category,
            'original_code': original,
            'fixed_code': fixed,
        })

os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
with open(OUT_CSV, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
    writer.writeheader()
    writer.writerows(rows_out)

print(f"\n=== Summary across {len(rows_out)} bugs ===")
from collections import Counter
counts = Counter(r['category'] for r in rows_out)
for cat, n in counts.most_common():
    print(f"  {cat}: {n} ({100*n/len(rows_out):.1f}%)")

print(f"\nSaved to {OUT_CSV}")

