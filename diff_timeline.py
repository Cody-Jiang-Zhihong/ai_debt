# diff_timeline.py (Incremental diff-based AI debt computation - optimized)
# Author: Cody

from __future__ import annotations

from pathlib import Path
import subprocess
import pickle
import hashlib
from typing import List, Dict

from models import TimeBucketMetrics, FileMetrics
from analyzers import analyze_file_text


# ---------------------------------------------------------------------
# Cache dirs
# ---------------------------------------------------------------------

# per-commit delta cache: sha -> float(delta_debt)
COMMIT_CACHE_DIR = Path(".ai_debt_cache_diff")
COMMIT_CACHE_DIR.mkdir(exist_ok=True)

# per-file-content cache: sha256(content) -> FileMetrics
FILE_CACHE_DIR = Path(".ai_debt_cache_file")
FILE_CACHE_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _run_git(root: Path, args) -> str:
    """
    Run a git command inside `root` and return stdout as text.
    We swallow stderr and don't crash the whole run on non-zero exit.
    """
    try:
        out = subprocess.check_output(
            ["git", "-C", str(root), *args],
            text=True,
            errors="ignore",
        )
        return out
    except Exception:
        return ""


def _hash_content(text: str) -> str:
    """
    Stable hash for file content so we can reuse expensive
    smell/AST analysis across commits.
    """
    h = hashlib.sha256()
    h.update(text.encode("utf-8", errors="ignore"))
    return h.hexdigest()


def _load_commit_delta(sha: str):
    p = COMMIT_CACHE_DIR / f"{sha}.pkl"
    if p.exists():
        try:
            with open(p, "rb") as f:
                return pickle.load(f)
        except Exception:
            return None
    return None


def _save_commit_delta(sha: str, delta: float) -> None:
    p = COMMIT_CACHE_DIR / f"{sha}.pkl"
    try:
        with open(p, "wb") as f:
            pickle.dump(delta, f)
    except Exception:
        # cache miss shouldn't break anything
        pass


def _load_file_metrics(content_hash: str) -> FileMetrics | None:
    p = FILE_CACHE_DIR / f"{content_hash}.pkl"
    if p.exists():
        try:
            with open(p, "rb") as f:
                return pickle.load(f)
        except Exception:
            return None
    return None


def _save_file_metrics(content_hash: str, fm: FileMetrics) -> None:
    p = FILE_CACHE_DIR / f"{content_hash}.pkl"
    try:
        with open(p, "wb") as f:
            pickle.dump(fm, f)
    except Exception:
        # best-effort only
        pass


def _analyze_content_with_cache(root: Path, commit_spec: str, rel_path: str) -> FileMetrics | None:
    """
    Load a file's content from git (commit_spec:path) and run AI debt
    analysis, with strong caching keyed by content hash.

    Returns FileMetrics or None on failure.
    """
    # commit_spec looks like "abc123:path/to/file.py"
    text = _run_git(root, ["show", commit_spec])
    if not text:
        return None

    content_hash = _hash_content(text)
    cached = _load_file_metrics(content_hash)
    if cached is not None:
        return cached

    fm = analyze_file_text(text, rel_path)
    _save_file_metrics(content_hash, fm)
    return fm


# ---------------------------------------------------------------------
# Core per-commit delta computation
# ---------------------------------------------------------------------


def compute_commit_ai_debt(root: Path, sha: str, parent: str) -> float:
    """
    Compute AI debt *introduced by this commit* by looking only at changed
    Python files between `parent` and `sha`.

    This version:
      - only diff .py files
      - uses content-hash cache to avoid re-running AST/smell analysis
        for identical file contents across commits.
    """
    root = Path(root)

    # 1. List changed files
    diff_out = _run_git(root, ["diff", "--name-status", parent, sha])
    if not diff_out:
        return 0.0

    changed: List[tuple[str, str]] = []
    for line in diff_out.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            status, path = parts[0], parts[1]
            if path.endswith(".py"):
                changed.append((status, path))

    if not changed:
        return 0.0

    debt_delta = 0.0

    # 2. For each changed file: compute before & after
    for status, rel_path in changed:
        before_score = 0.0
        after_score = 0.0

        # --- before ---
        if status != "A":  # not newly added
            fm_before = _analyze_content_with_cache(root, f"{parent}:{rel_path}", rel_path)
            if fm_before is not None:
                before_score = fm_before.ai_debt_score

        # --- after ---
        if status != "D":  # not deleted
            fm_after = _analyze_content_with_cache(root, f"{sha}:{rel_path}", rel_path)
            if fm_after is not None:
                after_score = fm_after.ai_debt_score

        debt_delta += (after_score - before_score)

    return debt_delta


# ---------------------------------------------------------------------
# Timeline construction
# ---------------------------------------------------------------------


def build_diff_timeline(root: Path, since: str = "2014-01-01") -> List[TimeBucketMetrics]:
    """
    Pure incremental debt timeline (optimized):

      - iterate commits on the mainline (first-parent) since `since`
      - compute per-commit AI debt delta (with heavy caching)
      - accumulate into a cumulative AI debt number
      - bucket by YYYY-MM (month); last commit in a month determines
        that month's cumulative AI debt.

    Compared to the original version:
      - avoids per-commit `git show` for the date (we parse dates once)
      - avoids per-commit `rev-list` for parents (we walk first-parent chain)
      - reuses FileMetrics via content-hash cache
    """
    root = Path(root).resolve()

    # 1. Get linear history (first-parent) with dates.
    #    Format: "<sha> <YYYY-MM-DD>"
    log_out = _run_git(
        root,
        ["log", f"--since={since}", "--first-parent", "--date=short", "--pretty=%H %ad"],
    )
    print("DEBUG git log out:\n", log_out[:500])
    if not log_out:
        return []

    entries: List[tuple[str, str]] = []
    for line in log_out.splitlines():
        parts = line.strip().split()
        if len(parts) < 2:
            continue
        sha, date = parts[0], parts[1]
        month = date[:7]  # "YYYY-MM"
        entries.append((sha, month))

    print("DEBUG entries count:", len(entries))
    if not entries:
        print("DEBUG: entries empty, first few log lines were:")
        for line in log_out.splitlines()[:5]:
            print("  ", repr(line))
        return []

    # Git log is newest->oldest; we want chronological
    entries = entries[::-1]

    timeline: Dict[str, float] = {}       # month -> cumulative debt
    month_commits: Dict[str, int] = {}    # month -> commit count (on mainline)

    total_debt = 0.0
    prev_sha: str | None = None

    for sha, month in entries:
        if prev_sha is None:
            # first commit in range: we don't know baseline debt before it,
            # so we treat its delta as 0 (i.e., use it as starting point).
            prev_sha = sha
            month_commits[month] = month_commits.get(month, 0) + 1
            timeline[month] = total_debt
            continue

        # Per-commit delta cache
        cached_delta = _load_commit_delta(sha)
        if cached_delta is not None:
            delta = cached_delta
        else:
            delta = compute_commit_ai_debt(root, sha, prev_sha)
            _save_commit_delta(sha, delta)

        total_debt += delta
        month_commits[month] = month_commits.get(month, 0) + 1
        timeline[month] = total_debt
        prev_sha = sha

    # 3. Convert to TimeBucketMetrics.
    #    We store cumulative AI debt in both sum & avg so the existing
    #    timeline chart (which uses ai_debt_avg) shows the right curve.
    buckets: List[TimeBucketMetrics] = []
    for month in sorted(timeline.keys()):
        debt = timeline[month]
        commits = month_commits.get(month, 0)
        buckets.append(
            TimeBucketMetrics(
                bucket=month,
                ai_debt_sum=debt,
                ai_debt_avg=debt,
                commits=commits,
            )
        )

    return buckets
