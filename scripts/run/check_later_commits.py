"""
Checklist item #1/#2: does the actual documented bug line get touched again
in a LATER commit, beyond Defects4J's designated fix commit?

Uses `defects4j query` to get each bug's official fix commit hash, then
`git log -L <line>,<line>:<file> <fix_hash>..HEAD` on the FULL repo (not the
stripped-down defects4j checkout, which has no git history) to see every
commit after the fix that touched that exact line.

This surfaces the commit list for manual review -- it doesn't judge whether
a later touch is a "real" further fix vs. just a refactor/formatting change,
that's the manual part Prof. Gulzar asked for.
"""

import subprocess
import csv
import os

BASE = os.path.expanduser("~/llm-bug-study/experiment")
REPO_DIR = os.path.expanduser("~/defects4j/project_repos")

PROJECT_REPO_NAMES = {
    "Chart": "jfreechart",
    "Lang": "commons-lang",
    "Math": "commons-math",
}

# Chart's local git mirror doesn't contain the pre-GitHub SVN history where
# these fix commits live, so its numeric revisions can't be resolved here.
# Swapping in two more Lang/Math bugs to keep a useful sample size.
SAMPLE_BUGS = [
    ("Lang", "6"),
    ("Lang", "9"),
    ("Math", "6"),
    ("Math", "11"),
    ("Math", "2"),
]

SOURCES = {
    "Chart": os.path.join(BASE, "results/java/results_v9_testfix.csv"),
    "Lang": os.path.join(BASE, "results/java/results_v9_testfix_lang.csv"),
    "Math": os.path.join(BASE, "results/java/results_v9_testfix_math.csv"),
}


def get_fixed_revision(project, bug_id):
    result = subprocess.run(
        ['defects4j', 'query', '-p', project, '-q', 'revision.id.fixed'],
        capture_output=True, text=True, timeout=60
    )
    for line in result.stdout.splitlines():
        parts = line.strip().split(',')
        if len(parts) >= 2 and parts[0] == bug_id:
            return parts[1]
    return None


def get_actual_line_and_file(project, bug_id):
    with open(SOURCES[project]) as f:
        rows = list(csv.DictReader(f))
    row = next((r for r in rows if r['bug_id'] == bug_id), None)
    if not row:
        return None, None
    import json
    data_path = os.path.join(BASE, "data/bugs", f"{project}_{bug_id}", "data.json")
    with open(data_path) as f:
        data = json.load(f)
    return int(row['actual_line']), data.get('file_path', '')


def find_last_commit_with_path(repo_path, file_path):
    """The most recent commit where this path GENUINELY EXISTS in the tree
    -- not just the last commit that touched it, since that could be the
    deletion commit itself, where the path is already gone."""
    result = subprocess.run(
        ['git', '--git-dir', repo_path, 'log', '--all', '--format=%H', '--', file_path],
        capture_output=True, text=True, timeout=60
    )
    for commit in result.stdout.splitlines():
        commit = commit.strip()
        if not commit:
            continue
        check = subprocess.run(
            ['git', '--git-dir', repo_path, 'cat-file', '-e', f'{commit}:{file_path}'],
            capture_output=True, text=True, timeout=30
        )
        if check.returncode == 0:
            return commit
    return None


def resolve_fixed_commit(project, repo_path, raw_revision):
    """
    For Lang/Math, defects4j query returns a real git SHA already.
    For Chart, it returns an old SVN revision number (JFreeChart's history
    predates its git mirror) -- resolve it to the git commit via the
    'git-svn-id: ...@<rev> ...' footer git-svn writes into each commit.
    """
    if len(raw_revision) >= 20:  # looks like a real git SHA already
        return raw_revision

    result = subprocess.run(
        ['git', '--git-dir', repo_path, 'log', '--all', '--format=%H %B',
         f'--grep=@{raw_revision} ', '-F'],
        capture_output=True, text=True, timeout=60
    )
    lines = [l for l in result.stdout.splitlines() if l.strip()]
    if lines:
        return lines[0].split()[0]
    return None


def find_real_path_in_repo(repo_path, commit_ref, file_path):
    """Try the stored file_path as-is, then common prefixes, checking BOTH
    the fix commit and HEAD (paths can shift between the two), then a full
    tree search by basename at HEAD if all else fails."""
    candidates = [
        file_path,
        f"src/main/java/{file_path}",
        f"source/{file_path}",
        f"src/{file_path}",
    ]
    for ref in [commit_ref, "HEAD"]:
        for candidate in candidates:
            check = subprocess.run(
                ['git', '--git-dir', repo_path, 'cat-file', '-e', f'{ref}:{candidate}'],
                capture_output=True, text=True, timeout=30
            )
            if check.returncode == 0:
                return candidate

    # fall back: search HEAD's tree for the basename
    basename = os.path.basename(file_path)
    result = subprocess.run(
        ['git', '--git-dir', repo_path, 'ls-tree', '-r', '--name-only', 'HEAD'],
        capture_output=True, text=True, timeout=60
    )
    matches = [l for l in result.stdout.splitlines() if l.endswith(basename)]
    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        print(f"  Multiple tree matches for {basename}: {matches}")
        return matches[0]
    return None


for project, bug_id in SAMPLE_BUGS:
    print(f"\n{'='*70}")
    print(f"=== {project}_{bug_id} ===")
    print(f"{'='*70}")

    actual_line, file_path = get_actual_line_and_file(project, bug_id)
    if actual_line is None or not file_path:
        print("  Could not find actual_line/file_path, skipping")
        continue

    raw_revision = get_fixed_revision(project, bug_id)
    if not raw_revision:
        print("  Could not find fixed revision, skipping")
        continue

    repo_path = os.path.join(REPO_DIR, PROJECT_REPO_NAMES[project] + ".git")
    if not os.path.exists(repo_path):
        print(f"  Repo not found at {repo_path}, skipping")
        continue

    fixed_rev = resolve_fixed_commit(project, repo_path, raw_revision)
    if not fixed_rev:
        print(f"  Could not resolve '{raw_revision}' to a git commit, skipping")
        continue

    real_path = find_real_path_in_repo(repo_path, fixed_rev, file_path)
    if not real_path:
        print(f"  Could not locate '{file_path}' (or a matching basename) in the repo at {fixed_rev[:10]}, skipping")
        continue

    print(f"  actual_line={actual_line}  file={real_path}")
    print(f"  fix commit: {raw_revision} -> resolved to {fixed_rev[:10]}")

    range_end = find_last_commit_with_path(repo_path, real_path)
    if not range_end:
        print(f"  Could not find any commit containing '{real_path}', skipping")
        continue
    if range_end != subprocess.run(
        ['git', '--git-dir', repo_path, 'rev-parse', 'HEAD'],
        capture_output=True, text=True, timeout=30
    ).stdout.strip():
        print(f"  Note: file no longer exists at HEAD -- using last commit that has it "
              f"({range_end[:10]}) as the range endpoint instead")

    cmd = [
        'git', '--git-dir', repo_path, 'log',
        f'-L{actual_line},{actual_line}:{real_path}',
        '--oneline', '--no-patch',
        f'{fixed_rev}..{range_end}'
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

    if result.returncode != 0:
        print(f"  git log failed: {result.stderr.strip()[:300]}")
        continue

    commits = [l for l in result.stdout.splitlines() if l.strip()]
    if not commits:
        print(f"  No later commits touch this exact line. "
              f"Line has been stable since the official fix.")
    else:
        print(f"  {len(commits)} later commit(s) touch this line:")
        for c in commits:
            print(f"    {c}")
        print(f"\n  To see the actual diffs, run:")
        print(f"    git --git-dir {repo_path} log -p -L{actual_line},{actual_line}:{real_path} {fixed_rev}..{range_end}")

print("\nDone.")

