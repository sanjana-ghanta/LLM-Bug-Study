"""
Pick the N usable bugs that `-n N` runs on.

The samples are nested: the bugs for a smaller N are always among the bugs for
a larger N, so raising N only adds bugs and every earlier result still counts.
(A plain random.Random(seed).sample(bugs, n) is not nested: Python switches
sampling algorithms as n grows, e.g. its N=100 sample drops 3 of the N=50 bugs.)

The first BASE_N bugs are exactly random.Random(seed).sample(bugs, BASE_N), the
sample every earlier "-n 50" run used, so those results stay valid. Bugs past
BASE_N follow one fixed random order of the remaining bugs.
"""
import json
import os
import random

BASE_N = 50


def usable_bugs(bugs_dir):
    """Bug dirs whose data.json has an original_bug_line, sorted by name."""
    out = []
    for d in sorted(os.listdir(bugs_dir)):
        try:
            with open(os.path.join(bugs_dir, d, "data.json")) as f:
                line = json.load(f).get("original_bug_line")
        except Exception:
            continue
        if line is not None:
            out.append(d)
    return out


def sample_bugs(bugs_dir, n, seed=0):
    """Set of n usable bug dirs (all of them if n exceeds the number usable)."""
    bugs = usable_bugs(bugs_dir)
    base = random.Random(seed).sample(bugs, min(BASE_N, len(bugs)))
    if n <= len(base):
        # Same as before for n <= BASE_N: keeps earlier small-N runs (e.g. smoke's n=2) reproducible.
        return set(random.Random(seed).sample(bugs, n))
    taken = set(base)
    rest = [b for b in random.Random(seed).sample(bugs, len(bugs)) if b not in taken]
    return set(base + rest[: n - len(base)])
