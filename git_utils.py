# git_utils.py
# Author: Cody
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple


def run_git(args: List[str], cwd: Path) -> str:
    # 运行 git 命令，返回 stdout
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def list_tracked_files(root: Path, exts: Tuple[str, ...] = (".py",)) -> List[Path]:
    # 列出被 git 跟踪的指定后缀文件
    out = run_git(["ls-files"], cwd=root)
    files = []
    for line in out.splitlines():
        p = root / line.strip()
        if p.suffix in exts:
            files.append(p)
    return files


def get_file_change_stats(root: Path, since: str) -> Dict[str, Dict[str, int]]:
    """统计自 since 以来每个文件新增/删除的行数。
    since 格式：'2024-01-01'
    返回: { "path/to/file.py": {"added": X, "deleted": Y, "total_added": Z} }
    """
    # 使用 git log --numstat
    out = run_git(
        ["log", f"--since={since}", "--numstat", "--format=commit %H"], cwd=root
    )
    stats: Dict[str, Dict[str, int]] = {}
    current_commit = None
    for line in out.splitlines():
        if line.startswith("commit "):
            current_commit = line.split()[1]
            continue
        parts = line.split()
        if len(parts) != 3:
            continue
        added, deleted, path = parts
        if added == "-" or deleted == "-":
            # 二进制文件
            continue
        try:
            a = int(added)
            d = int(deleted)
        except ValueError:
            continue
        file_stat = stats.setdefault(path, {"added": 0, "deleted": 0})
        file_stat["added"] += a
        file_stat["deleted"] += d
    return stats


def get_time_buckets(root: Path, since: str, granularity: str = "month"):
    """按时间桶聚合：
    返回:
    {
        "YYYY-MM": {
            "commits": set([...]),
            "loc_added": int,
            "files": {
                "path/to/file.py": {"added": int, "deleted": int}
            }
        },
        ...
    }
    """
    out = run_git(
        ["log", f"--since={since}", "--date=short", "--format=%cd %H", "--numstat"],
        cwd=root,
    )

    buckets = {}
    current_date = None
    current_hash = None

    for line in out.splitlines():
        # 日期+commit 行：YYYY-MM-DD <hash>
        if line and len(line.split()) == 2 and line[4] == "-":
            date_str, commit_hash = line.split()
            current_date = date_str
            current_hash = commit_hash
            continue

        parts = line.split()
        if len(parts) != 3:
            continue

        added, deleted, path = parts
        if added == "-" or deleted == "-":
            # binary
            continue

        try:
            a = int(added)
            d = int(deleted)
        except ValueError:
            continue

        if granularity == "month":
            bucket = current_date[:7]  # "YYYY-MM"
        else:
            bucket = current_date

        info = buckets.setdefault(
            bucket,
            {"commits": set(), "loc_added": 0, "files": {}},
        )
        info["commits"].add(current_hash)
        info["loc_added"] += a

        fstat = info["files"].setdefault(path, {"added": 0, "deleted": 0})
        fstat["added"] += a
        fstat["deleted"] += d

    return buckets



def get_merge_commits(root: Path, main_branch: str = "main") -> List[str]:
    """MVP: 用 merge commit 近似 PR"""
    try_branches = [main_branch, "master"]
    branch = None
    for b in try_branches:
        try:
            run_git(["rev-parse", b], cwd=root)
            branch = b
            break
        except subprocess.CalledProcessError:
            continue
    if not branch:
        return []
    out = run_git(["log", branch, "--merges", "--format=%H"], cwd=root)
    return [line.strip() for line in out.splitlines() if line.strip()]


def get_merge_diff_stats(root: Path, merge_hash: str) -> Dict[str, int]:
    """返回某个 merge commit 的每文件新增行数"""
    out = run_git(["show", "--numstat", "--format=", merge_hash], cwd=root)
    stats = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) != 3:
            continue
        added, deleted, path = parts
        if added == "-" or deleted == "-":
            continue
        try:
            a = int(added)
        except ValueError:
            continue
        stats[path] = stats.get(path, 0) + a
    return stats
