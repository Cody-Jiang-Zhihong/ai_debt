# analyzers.py
# Author: Cody
"""
File-level analysis pipeline.

Input:  a filesystem path to a Python file
Output: FileMetrics with:
    - loc
    - ai_influence
    - ai_debt_score
    - smell breakdown
    - recent_added (currently 0; Git integration can be added later)
"""

from __future__ import annotations

from pathlib import Path

from models import FileMetrics, SmellScores
from smells import analyze_smells


def compute_ai_debt(smell: SmellScores) -> float:
    """
    Heuristic AI tech-debt score in [0, 1].

    We weight smells roughly by how "AI-ish" and risky they are:
      - duplicate_blocks: 0.4
      - api_hallucinations: 0.3
      - over_engineering: 0.15
      - unnecessary_abstractions: 0.10
      - silent_failures: 0.05
    """
    raw = (
        0.4 * smell.duplicate_blocks
        + 0.3 * smell.api_hallucinations
        + 0.15 * smell.over_engineering
        + 0.10 * smell.unnecessary_abstractions
        + 0.05 * smell.silent_failures
    )

    # Map to [0, 1] with a soft cap.
    return min(1.0, raw / 10.0)


def compute_ai_influence(smell: SmellScores) -> float:
    """
    Rough proxy for 'how much this file feels AI-generated'.

    We use the presence and volume of smells as a signal.
    This is NOT meant to be a classifier, just a heuristic score.
    """
    total = (
        smell.duplicate_blocks
        + smell.api_hallucinations
        + smell.over_engineering
        + smell.unnecessary_abstractions
        + smell.silent_failures
    )

    if total <= 0:
        return 0.0

    # Ensure small but non-zero influence when we have any smell.
    return max(0.1, min(1.0, total / 20.0))


def analyze_file(path: Path) -> FileMetrics:
    """
    Main entry point used by scanner.scan_repo.

    path: absolute or relative Path to a .py file
    """
    path = Path(path)

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        text = ""

    # Simple LOC metric (can be replaced with SLOC later).
    loc = len(text.splitlines())

    smells = analyze_smells(text)
    ai_debt = compute_ai_debt(smells)
    ai_influence = compute_ai_influence(smells)

    # Git-based "recent added LOC" is not wired yet.
    recent_added = 0

    return FileMetrics(
        path=str(path),
        loc=loc,
        ai_influence=ai_influence,
        ai_debt_score=ai_debt,
        smell=smells,
        recent_added=recent_added,
    )
