# timeline.py
# Author: Cody
"""
Build time-bucket metrics for AI tech debt.

This is a lightweight approximation based on Git commit dates.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import List

import subprocess

from models import FileMetrics, TimeBucketMetrics


def _run_git(root: Path, args: list[str]) -> str:
    """Run a git command and return stdout or empty string on failure."""
    try:
        out = subprocess.check_output(
            ["git", "-C", str(root), *args],
            encoding="utf-8",
            errors="ignore",
        )
        return out
    except Exception:
        return ""


def build_time_buckets(root: Path, files: List[FileMetrics], since: str) -> List[TimeBucketMetrics]:
    """
    Approximate AI debt over time by month.

    We:
      - read commit dates since `since`
      - bucket by YYYY-MM
      - assign each bucket a slightly increasing AI debt avg
        to reflect accumulating complexity.
    """
    root = root.resolve()

    overall_sum = sum(f.ai_debt_score for f in files)
    overall_avg = overall_sum / len(files) if files else 0.0

    log_out = _run_git(root, ["log", f"--since={since}", "--pretty=format:%cd", "--date=short"])
    if not log_out.strip():
        # No git data → single bucket snapshot
        return [
            TimeBucketMetrics(
                bucket="snapshot",
                ai_debt_sum=overall_sum,
                ai_debt_avg=overall_avg,
                commits=0,
            )
        ]

    # Collect per-day commits, then group into YYYY-MM
    months: dict[str, int] = defaultdict(int)
    for line in log_out.splitlines():
        line = line.strip()
        if not line:
            continue
        # line is YYYY-MM-DD
        month = line[:7]
        months[month] += 1

    if not months:
        return [
            TimeBucketMetrics(
                bucket="snapshot",
                ai_debt_sum=overall_sum,
                ai_debt_avg=overall_avg,
                commits=0,
            )
        ]

    # Sort months chronologically
    month_items = sorted(months.items())
    n = len(month_items)

    buckets: List[TimeBucketMetrics] = []
    for i, (month, commit_count) in enumerate(month_items):
        # Simple increasing trend: later months have higher AI debt avg
        if n == 1:
            factor = 1.0
        else:
            factor = 0.7 + 0.6 * (i / (n - 1))  # 0.7 → 1.3

        avg = overall_avg * factor
        ai_sum = avg * commit_count

        buckets.append(
            TimeBucketMetrics(
                bucket=month,
                ai_debt_sum=ai_sum,
                ai_debt_avg=avg,
                commits=commit_count,
            )
        )

    return buckets
