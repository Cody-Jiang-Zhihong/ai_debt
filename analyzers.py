# analyzers.py (v2 — compatible with scanner v3)
# Author: Cody

"""
File-level analysis pipeline with extended parameters.

This version is compatible with scanner.scan_repo(root)
which calls analyze_file(path, rel_path, stats, max_added).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from models import FileMetrics, SmellScores
from smells import analyze_smells


# =========================================================
# Calculation helpers
# =========================================================

def compute_ai_debt(smell: SmellScores) -> float:
    raw = (
        0.4 * smell.duplicate_blocks
        + 0.3 * smell.api_hallucinations
        + 0.15 * smell.over_engineering
        + 0.10 * smell.unnecessary_abstractions
        + 0.05 * smell.silent_failures
    )
    return min(1.0, raw / 10.0)


def compute_ai_influence(smell: SmellScores) -> float:
    total = (
        smell.duplicate_blocks
        + smell.api_hallucinations
        + smell.over_engineering
        + smell.unnecessary_abstractions
        + smell.silent_failures
    )
    if total <= 0:
        return 0.0
    return max(0.1, min(1.0, total / 20.0))


# =========================================================
# File content analysis (used by diff engine)
# =========================================================

def analyze_file_text(text: str, rel_path: str) -> FileMetrics:
    """Analyze file via raw text, used for diff-based logic."""
    loc = len(text.splitlines()) if text else 0
    smells = analyze_smells(text)
    ai_debt = compute_ai_debt(smells)
    ai_influence = compute_ai_influence(smells)

    return FileMetrics(
        path=rel_path,
        loc=loc,
        ai_influence=ai_influence,
        ai_debt_score=ai_debt,
        smell=smells,
        recent_added=0,
    )


# =========================================================
# Main function used by scanner.scan_repo
# =========================================================

def analyze_file(
    path: str,
    rel_path: Optional[str] = None,
    stats=None,
    max_added: int = 0,
) -> FileMetrics:
    """
    Compatible entry point for scanner.v3

    Parameters:
        path: absolute filesystem path
        rel_path: repository-relative path
        stats: reserved for future Git stats
        max_added: reserved for future Git analysis
    """
    p = Path(path)

    try:
        text = p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        text = ""

    rel = rel_path if rel_path is not None else str(p)

    loc = len(text.splitlines())
    smells = analyze_smells(text)
    ai_debt = compute_ai_debt(smells)
    ai_influence = compute_ai_influence(smells)

    # stats / max_added will be wired later
    return FileMetrics(
        path=rel,
        loc=loc,
        ai_influence=ai_influence,
        ai_debt_score=ai_debt,
        smell=smells,
        recent_added=max_added,
    )
