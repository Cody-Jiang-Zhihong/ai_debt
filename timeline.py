# timeline.py
# Author: Cody
from __future__ import annotations

import pickle
import subprocess
from pathlib import Path
from typing import List, Dict

from models import TimeBucketMetrics
from scanner import scan_repo

# Where we cache per-commit snapshot metrics
CACHE_DIR = Path(".ai_debt_cache")
CACHE_DIR.mkdir(exist_ok=True)


def _run_git(root: Path, args: List[str]) -> str:
    """Run a git command and return stdout as text."""
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _collect_month_end_commits(root: Path, since: str) -> Dict[str, dict]:
    """
    Collect one representative commit per month since `since`.

    Returns: { "YYYY-MM": {"sha": <commit>, "count": <commits_in_month>} }
    """
    # --date=short →  YYYY-MM-DD
    log_output = _run_git(
        root,
        ["log", f"--since={since}", "--date=short", "--pretty=%H %ad"],
    )

    month_info: Dict[str, dict] = {}

    for line in log_output.splitlines():
        line = line.strip()
        if not line:
            continue

        parts = line.split()
        if len(parts) != 2:
            # unexpected format, skip
            continue

        sha, date = parts
        month = date[:7]  # "YYYY-MM"

        info = month_info.get(month)
        if info is None:
            # First commit we see in this month.
            # Because git log is reverse-chronological, this is the *last* commit of that month.
            month_info[month] = {"sha": sha, "count": 1, "date": date}
        else:
            info["count"] += 1

    return month_info


def _load_cache(sha: str):
    path = CACHE_DIR / f"{sha}.pkl"
    if path.exists():
        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except Exception:
            return None
    return None


def _save_cache(sha: str, data):
    path = CACHE_DIR / f"{sha}.pkl"
    try:
        with open(path, "wb") as f:
            pickle.dump(data, f)
    except Exception:
        # Cache failures should never break the run
        pass


def build_time_buckets(
    root: Path,
    file_metrics,            # kept for CLI compatibility, not used here
    since: str = "2020-01-01",
) -> List[TimeBucketMetrics]:
    """
    Build AI debt timeline using monthly snapshot sampling + per-commit cache.

    For each month between `since` and HEAD:
      - pick the last commit of that month
      - if we have cached (sum, avg) for that SHA, reuse it
      - otherwise:
          * checkout that commit
          * run scan_repo(root)
          * compute total/average AI debt
          * save to .ai_debt_cache/<sha>.pkl
    """
    root = Path(root).resolve()

    # Save current HEAD so we can restore it later
    current_head = _run_git(root, ["rev-parse", "HEAD"])

    # Collect representative commits
    month_info = _collect_month_end_commits(root, since)
    if not month_info:
        return []

    months_sorted = sorted(month_info.keys())
    buckets: List[TimeBucketMetrics] = []

    try:
        for month in months_sorted:
            info = month_info[month]
            sha = info["sha"]
            commits_in_month = info["count"]

            # 1) Try to load cached snapshot metrics
            cached = _load_cache(sha)
            if cached is not None:
                total_debt, avg_debt = cached
            else:
                # 2) Checkout this snapshot and recompute
                subprocess.run(
                    ["git", "-C", str(root), "checkout", "--quiet", sha],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=True,
                )
                snapshot_files = scan_repo(root)
                total_debt = sum(f.ai_debt_score for f in snapshot_files)
                avg_debt = total_debt / len(snapshot_files) if snapshot_files else 0.0

                # 3) Save to cache
                _save_cache(sha, (total_debt, avg_debt))

            buckets.append(
                TimeBucketMetrics(
                    bucket=month,
                    ai_debt_sum=total_debt,
                    ai_debt_avg=avg_debt,
                    commits=commits_in_month,
                )
            )

    finally:
        # Always try to restore original HEAD
        try:
            subprocess.run(
                ["git", "-C", str(root), "checkout", "--quiet", current_head],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
        except Exception:
            # Don't hard-fail if restore fails
            pass

    return buckets
