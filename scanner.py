# scanner.py
# Author: Cody
from pathlib import Path
from typing import List, Dict
from models import FileMetrics, TimeBucketMetrics, PRMetrics
from git_utils import (
    list_tracked_files,
    get_file_change_stats,
    get_time_buckets,
    get_merge_commits,
    get_merge_diff_stats,
)
from analyzers import analyze_file


def scan_repo(root: Path, since: str = "2023-01-01"):
    # 1. Git stats
    file_change_stats = get_file_change_stats(root, since)
    max_added = max([v["added"] for v in file_change_stats.values()] or [1])

    # 2. 文件级扫描
    tracked_files = list_tracked_files(root, exts=(".py",))
    file_metrics: List[FileMetrics] = []

    for f in tracked_files:
        rel = str(f.relative_to(root))
        stats = file_change_stats.get(rel, {"added": 0, "deleted": 0})
        metrics = analyze_file(root, rel, stats, max_added)
        file_metrics.append(metrics)

    # 3. 时间趋势：按月份聚合
    buckets_raw = get_time_buckets(root, since, granularity="month")
    bucket_metrics: List[TimeBucketMetrics] = []

    # 为了快速查找，建一个 path -> FileMetrics 的索引
    fm_by_path = {fm.path.replace("\\", "/"): fm for fm in file_metrics}

    for bucket, info in buckets_raw.items():
        commits = info["commits"]
        loc_added = info["loc_added"]
        files_stats = info.get("files", {})

        debt_weighted_sum = 0.0
        added_total_for_weight = 0

        for path, st in files_stats.items():
            norm_path = path.replace("\\", "/")
            fm = fm_by_path.get(norm_path)
            if not fm:
                continue
            a = st.get("added", 0)
            if a <= 0:
                continue
            debt_weighted_sum += fm.ai_debt_score * a
            added_total_for_weight += a

        if added_total_for_weight > 0:
            avg_ai_debt = debt_weighted_sum / added_total_for_weight
        else:
            # 桶里虽然有 commit，但没 Python 文件的变更
            avg_ai_debt = 0.0

        bucket_metrics.append(
            TimeBucketMetrics(
                bucket=bucket,
                ai_debt_sum=debt_weighted_sum,
                ai_debt_avg=avg_ai_debt,
                commits=len(commits),
            )
        )


    # 4. PR 风险：用 merge commit 近似
    pr_metrics: List[PRMetrics] = []
    merges = get_merge_commits(root)
    for mh in merges:
        diff_stats = get_merge_diff_stats(root, mh)
        loc_added = sum(diff_stats.values())
        files_touched = len(diff_stats)

        debt_delta = 0.0
        top_files = []

        for path, added in diff_stats.items():
            norm_path = path.replace("\\", "/")
            fm = next((f for f in file_metrics if f.path.replace("\\", "/") == norm_path), None)
            if fm:
                debt_delta += fm.ai_debt_score * added
                top_files.append(norm_path)

        pr_metrics.append(
            PRMetrics(
                identifier=mh[:8],
                files_touched=files_touched,
                loc_added=loc_added,
                ai_debt_delta=debt_delta,
                ai_risk_index=0.0,  # 暂时占位，下面统一归一化
                top_files=top_files[:5],
            )
        )

    # 统一归一化 PR 风险指数，让最大为 1，其它在 0-1 内
    if pr_metrics:
        max_loc = max(p.loc_added for p in pr_metrics) or 1
        max_debt = max(p.ai_debt_delta for p in pr_metrics) or 1

        for p in pr_metrics:
            norm_loc = p.loc_added / max_loc
            norm_debt = p.ai_debt_delta / max_debt if max_debt > 0 else 0.0
            # 权重：行数 40%，技术债 60%
            raw_risk = 0.4 * norm_loc + 0.6 * norm_debt
            p.ai_risk_index = raw_risk  # 已在 0-1 之间


    return file_metrics, bucket_metrics, pr_metrics
