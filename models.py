# models.py
# Author: Cody

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class SmellScores:
    """
    Raw smell counts for one file.
    These are integer counts, not normalized.
    """
    duplicate_blocks: int = 0
    api_hallucinations: int = 0
    over_engineering: int = 0
    unnecessary_abstractions: int = 0
    silent_failures: int = 0


@dataclass
class FileMetrics:
    """
    Per-file metrics written into files.csv
    """
    path: str
    loc: int
    ai_influence: float
    ai_debt_score: float

    # Smell detail
    smell: SmellScores

    # Git metadata
    recent_added: int

    def to_csv_row(self):
        return {
            "path": self.path,
            "loc": self.loc,
            "ai_influence": self.ai_influence,
            "ai_debt": self.ai_debt_score,
            "dup": self.smell.duplicate_blocks,
            "api": self.smell.api_hallucinations,
            "over_eng": self.smell.over_engineering,
            "unnecessary_abs": self.smell.unnecessary_abstractions,
            "silent": self.smell.silent_failures,
            "recent_added": self.recent_added,
        }


@dataclass
class TimeBucketMetrics:
    bucket: str
    ai_debt_sum: float
    ai_debt_avg: float
    commits: int


@dataclass
class PRMetrics:
    identifier: str
    files_touched: int
    loc_added: int
    ai_debt_delta: float
    ai_risk_index: float
    top_files: List[str]
    semantic_drift: float = 0.0  # NEW: semantic drift score in [0, 1]