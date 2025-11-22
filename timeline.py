# timeline.py
# Author: Cody
from __future__ import annotations

from pathlib import Path
from typing import List, Dict
import subprocess

from models import TimeBucketMetrics
from scanner import scan_repo


def _run_git(root: Path, args: List[str]) -> str:
    """Run a git command and return stdout as text."""
    result = subprocess.run(
        ["git"] + args,
        cwd=root,
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
        try:
            sha, date = line.split()
        except ValueError:
            # unexpected format, skip
            continue

        month = date[:7]  # "YYYY-MM"
        info = month_info.get(month)
        if info is None:
            # first commit we see in this month
            month_info[month] = {"sha": sha, "count": 1, "date": date}
        else:
            # commits are in reverse-chronological order by default,
            # so the *first* one in the month is actually the last commit.
            info["count"] += 1

    return month_info


def build_time_buckets(
    root: Path,
    file_metrics,  # kept for backward compatibility, not used in v2
    since: str = "2020-01-01",
) -> List[TimeBucketMetrics]:
    """
    Build AI debt timeline using monthly snapshot sampling (v2).

    For each month between `since` and HEAD:
      - pick the last commit of that month
      - checkout to that commit
      - run scan_repo(root) to recompute AI debt at that time
    """
    root = Path(root)

    # 1. 保存当前 HEAD，最后要切回去
    current_head = _run_git(root, ["rev-parse", "HEAD"])

    # 2. 收集每个月的代表 commit
    month_info = _collect_month_end_commits(root, since)

    # 没有历史就直接返回空
    if not month_info:
        return []

    # 3. 按时间顺序排序月份
    months_sorted = sorted(month_info.keys())

    buckets: List[TimeBucketMetrics] = []

    try:
        for month in months_sorted:
            info = month_info[month]
            sha = info["sha"]
            commits_in_month = info["count"]

            # 切到该月最后的 commit
            subprocess.run(
                ["git", "checkout", "--quiet", sha],
                cwd=root,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )

            # 对该快照重新分析整个仓库
            snapshot_files = scan_repo(root)

            total_debt = sum(f.ai_debt_score for f in snapshot_files)
            avg_debt = total_debt / len(snapshot_files) if snapshot_files else 0.0

            buckets.append(
                TimeBucketMetrics(
                    bucket=month,
                    ai_debt_sum=total_debt,
                    ai_debt_avg=avg_debt,
                    commits=commits_in_month,
                )
            )

    finally:
        # 无论中间是否报错，都尝试切回原来的 HEAD
        try:
            subprocess.run(
                ["git", "checkout", "--quiet", current_head],
                cwd=root,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
        except Exception:
            # 如果恢复失败，不再继续抛异常，以免把用户卡死
            pass

    return buckets
