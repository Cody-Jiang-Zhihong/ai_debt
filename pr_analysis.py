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
from drift import compute_pr_semantic_drift


def _run_git(root: Path, args: List[str]) -> str:
    """Run a git command in `root` and return stdout as text."""
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
    Build a robust index from repo-relative paths to FileMetrics.

    We try to support multiple possible `fm.path` styles:
      - absolute paths inside `root`
      - repo-relative paths like "thefuck/cli.py"
      - bare filenames like "cli.py"

    The main keys are repo-relative ("tests/foo.py"). We also keep
    a secondary index by filename so PRs are not dropped just because
    of a minor path mismatch.
    """
    root = root.resolve()
    index: Dict[str, FileMetrics] = {}

    for fm in files:
        p = Path(fm.path)

        # Try to interpret as absolute path under the repo
        rel = None
        if p.is_absolute():
            try:
                rel = p.resolve().relative_to(root)
            except Exception:
                rel = None

        # If that failed, treat it as already repo-relative
        if rel is None:
            if not p.is_absolute():
                rel = p
            else:
                # Last fallback: just store under filename
                rel = Path(p.name)

        rel_str = str(rel).replace("\\", "/")
        index[rel_str] = fm

        # Also index by plain filename (useful for fuzzy matching)
        fname = rel.name
        if fname and fname not in index:
            index[fname] = fm

    return index


def build_pr_metrics(root: Path, files: List[FileMetrics], since: str) -> List[PRMetrics]:
    """
    Analyze merge commits as PRs and compute risk metrics.

    root   : repo root
    files  : list of FileMetrics from current HEAD
    since  : git --since=... filter
    """
    root = Path(root).resolve()
    index = _build_file_index(root, files)

    # 1) Get merge commits as PR proxies
    log_out = _run_git(root, ["log", "--merges", f"--since={since}", "--pretty=format:%H"])
    merges = [line.strip() for line in log_out.splitlines() if line.strip()]

    if not merges:
        # Fallback: use last ~50 commits if there are no merges
        log_out = _run_git(root, ["log", "-n", "50", "--pretty=format:%H"])
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

            # Binary files or special entries
            if added_str == "-":
                continue

            try:
                added = int(added_str)
            except ValueError:
                continue

            loc_added += added
            rel = path_str.replace("\\", "/")

            # ---- Robust lookup: full path → tail → filename ----
            fm = None
            candidates = [
                rel,
                "/".join(rel.split("/")[-2:]),  # keep last 2 segments
                Path(rel).name,                # filename only
            ]
            for key in candidates:
                if key in index:
                    fm = index[key]
                    break

            if fm is None:
                # If we cannot map this file to FileMetrics, we just
                # ignore it for debt aggregation, but still count LOC.
                continue

            files_touched += 1
            touched_fms.append(fm)

        # If we found no matching FileMetrics, keep going but
        # with a very low-risk PR (so it still appears in charts).
        if not touched_fms:
            semantic_drift = compute_pr_semantic_drift(root, commit, [])
            pr_results.append(
                PRMetrics(
                    identifier=commit,
                    files_touched=0,
                    loc_added=loc_added,
                    ai_debt_delta=0.0,
                    ai_risk_index=0.01,
                    semantic_drift=semantic_drift,
                    top_files=[],
                )
            )
            continue

        # Aggregate AI debt of affected files
        avg_debt = sum(f.ai_debt_score for f in touched_fms) / len(touched_fms)
        debt_delta = avg_debt * max(1, loc_added) ** 0.5  # sub-linear with size

        # Risk index in [0, 1]
        risk = min(1.0, 0.02 * files_touched + debt_delta / 50.0)

        # Top 5 debt files touched by this PR
        unique_paths = {f.path for f in touched_fms}
        top_files = sorted(
            unique_paths,
            key=lambda p: next((f.ai_debt_score for f in touched_fms if f.path == p), 0.0),
            reverse=True,
        )[:5]

        # >>> IMPORTANT: pass file paths into semantic drift <<<
        drift_paths = [f.path for f in touched_fms]
        semantic_drift = compute_pr_semantic_drift(root, commit, drift_paths)

        pr_results.append(
            PRMetrics(
                identifier=commit,
                files_touched=files_touched,
                loc_added=loc_added,
                ai_debt_delta=debt_delta,
                ai_risk_index=risk,
                semantic_drift=semantic_drift,
                top_files=top_files,
            )
        )

    # Sort PRs by risk descending so the bar chart shows the riskiest ones first.
    pr_results.sort(key=lambda p: p.ai_risk_index, reverse=True)
    return pr_results
