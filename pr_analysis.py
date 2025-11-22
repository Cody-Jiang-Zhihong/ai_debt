# pr_analysis.py
# Author: Cody
"""
Compute PR-level risk metrics from Git history.

We treat merge commits as "PRs" and approximate their AI tech debt
impact based on changed files and their AI debt scores.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import subprocess

from models import FileMetrics, PRMetrics


def _run_git(root: Path, args: list[str]) -> str:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(root), *args],
            encoding="utf-8",
            errors="ignore",
        )
        return out
    except Exception:
        return ""


def _build_file_index(root: Path, files: List[FileMetrics]) -> Dict[str, FileMetrics]:
    """
    Map repo-relative paths ("thefuck/cli.py") to FileMetrics.
    """
    root = root.resolve()
    index: Dict[str, FileMetrics] = {}

    for fm in files:
        try:
            rel = Path(fm.path).resolve().relative_to(root)
            rel_str = str(rel).replace("\\", "/")
        except ValueError:
            rel_str = Path(fm.path).name
        index[rel_str] = fm

    return index


def build_pr_metrics(root: Path, files: List[FileMetrics], since: str) -> List[PRMetrics]:
    root = root.resolve()
    index = _build_file_index(root, files)

    # Get merge commits as PR proxies
    log_out = _run_git(root, ["log", "--merges", f"--since={since}", "--pretty=format:%H"])
    merges = [line.strip() for line in log_out.splitlines() if line.strip()]

    if not merges:
        # Fallback: use last ~20 commits if there are no merges
        log_out = _run_git(root, ["log", "-n", "20", "--pretty=format:%H"])
        merges = [line.strip() for line in log_out.splitlines() if line.strip()]

    pr_results: List[PRMetrics] = []

    for commit in merges:
        show_out = _run_git(root, ["show", "--numstat", "--pretty=format:", commit])
        if not show_out:
            continue

        files_touched = 0
        loc_added = 0
        touched_fms: List[FileMetrics] = []

        for line in show_out.splitlines():
            line = line.strip()
            if not line:
                continue

            parts = line.split("\t")
            if len(parts) != 3:
                continue

            added_str, _deleted_str, path_str = parts
            if added_str == "-":  # binary file
                continue

            try:
                added = int(added_str)
            except ValueError:
                continue

            loc_added += added
            rel = path_str.replace("\\", "/")

            fm = index.get(rel)
            if fm is None:
                continue

            files_touched += 1
            touched_fms.append(fm)

        if not touched_fms:
            continue

        # Aggregate AI debt of affected files
        avg_debt = sum(f.ai_debt_score for f in touched_fms) / len(touched_fms)
        debt_delta = avg_debt * max(1, loc_added) ** 0.5  # sub-linear with size

        # Risk index in [0, 1]
        risk = min(1.0, 0.02 * files_touched + debt_delta / 50.0)

        top_files = sorted(
            {f.path for f in touched_fms},
            key=lambda p: next((f.ai_debt_score for f in touched_fms if f.path == p), 0),
            reverse=True,
        )[:5]

        pr_results.append(
            PRMetrics(
                identifier=commit,
                files_touched=files_touched,
                loc_added=loc_added,
                ai_debt_delta=debt_delta,
                ai_risk_index=risk,
                top_files=top_files,
            )
        )

    # Sort PRs by risk descending
    pr_results.sort(key=lambda p: p.ai_risk_index, reverse=True)
    return pr_results
