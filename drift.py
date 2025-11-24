# drift.py
# Author: Cody
"""
Semantic drift detection for PRs.

For each PR (approximated by a commit), we compare old vs new versions of
the touched Python files and compute a 0–1 semantic drift score.

0.0 = no meaningful change
1.0 = completely rewritten / highly divergent
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

import difflib
import subprocess


def _run_git_show(root: Path, spec: str) -> str:
    """
    Read file content from git, e.g. 'commit:path/to/file.py'.

    Returns empty string on any failure.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "show", spec],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            encoding="utf-8",
            errors="ignore",
            check=False,
        )
        if proc.returncode != 0:
            return ""
        return proc.stdout
    except Exception:
        return ""



def _normalize_paths(root: Path, paths: Iterable[str]) -> List[str]:
    """
    Normalize file paths to repo-relative, forward-slash style.
    """
    norm: List[str] = []
    root = root.resolve()

    for p in paths:
        p = p.replace("\\", "/")
        # If already looks relative, keep it; otherwise try to relativize
        path_obj = Path(p)
        try:
            rel = path_obj.resolve().relative_to(root)
            rel_str = str(rel).replace("\\", "/")
        except Exception:
            rel_str = p
        norm.append(rel_str)

    return norm


def _file_drift(old: str, new: str) -> float:
    """
    Compute a simple semantic drift between two text blobs.

    Uses difflib.SequenceMatcher on raw text (including comments).
    """
    if not old and not new:
        return 0.0
    if old == new:
        return 0.0

    # Optionally we could strip very long whitespace runs, etc.
    sm = difflib.SequenceMatcher(None, old, new)
    similarity = sm.ratio()  # 0–1
    drift = 1.0 - similarity
    # Clamp safety
    if drift < 0.0:
        drift = 0.0
    elif drift > 1.0:
        drift = 1.0
    return drift


def compute_pr_semantic_drift(
    root: Path,
    commit: str,
    paths: Iterable[str],
    max_files: int = 30,
) -> float:
    """
    Compute a PR-level semantic drift score in [0, 1].

    Strategy:
    - Take the touched Python files (up to max_files).
    - For each file, compare:
        old = `commit^1:path`
        new = `commit:path`
      via SequenceMatcher.
    - Aggregate file-level drift with a simple average.

    If we cannot compute drift for any file, returns 0.0 (conservative).
    """
    root = root.resolve()
    rel_paths = _normalize_paths(root, paths)

    # Focus on .py files only; other assets are ignored for semantic drift.
    py_paths = [p for p in rel_paths if p.endswith(".py")]
    if not py_paths:
        return 0.0

    # Limit cost for huge PRs
    py_paths = py_paths[:max_files]

    drifts: List[float] = []

    for rel in py_paths:
        # `commit^1` is the first parent of the merge (or previous commit)
        old_spec = f"{commit}^1:{rel}"
        new_spec = f"{commit}:{rel}"

        old_src = _run_git_show(root, old_spec)
        new_src = _run_git_show(root, new_spec)

        # If we can't read either side, skip this file
        if not old_src and not new_src:
            continue

        d = _file_drift(old_src, new_src)
        drifts.append(d)

    if not drifts:
        # Could not compute for any file → treat as "unknown", default 0.0
        return 0.0

    avg = sum(drifts) / len(drifts)
    # Safety clamp
    if avg < 0.0:
        avg = 0.0
    elif avg > 1.0:
        avg = 1.0
    return avg
