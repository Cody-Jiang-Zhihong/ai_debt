# scanner.py
# Author: Cody
"""
Recursive repository scanner.
Collects Python files and passes them to analyzers.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

from analyzers import analyze_file
from models import FileMetrics

EXCLUDE_DIRS = {
    ".git",
    ".github",
    "__pycache__",
    "venv",
    "env",
    "build",
    "dist",
    "node_modules",
    ".idea",
    ".vscode",
}


def _is_excluded(path: Path) -> bool:
    """Return True if this path should be skipped entirely."""
    return any(part in EXCLUDE_DIRS for part in path.parts)


def scan_repo(root: Path) -> List[FileMetrics]:
    """
    Recursively scan a repository and analyze all *.py files.

    Returns a list of FileMetrics (one per file).
    """
    root = root.resolve()
    results: List[FileMetrics] = []

    for dirpath, dirnames, filenames in os.walk(root):
        dirpath_obj = Path(dirpath)

        if _is_excluded(dirpath_obj):
            # prune traversal
            dirnames[:] = []
            continue

        for fname in filenames:
            if not fname.endswith(".py"):
                continue

            fpath = dirpath_obj / fname
            metrics = analyze_file(fpath)
            results.append(metrics)

    return results
