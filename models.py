# models.py
# Author: Cody
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class FileSmells:
    # 大规模重复代码
    duplicate_blocks: int = 0
    # API 幻觉
    api_hallucinations: int = 0
    # 过度工程化
    over_engineering: int = 0
    # 不必要的抽象
    unnecessary_abstractions: int = 0
    # silent failure
    silent_failures: int = 0


@dataclass
class FileMetrics:
    path: str
    language: str
    loc: int
    ai_influence_score: float
    ai_debt_score: float
    smells: FileSmells
    # Git 相关
    recent_loc_added: int = 0
    total_loc_added: int = 0


@dataclass
class TimeBucketMetrics:
    # 某个时间段（例如按周）
    bucket: str  # e.g. "2024-10"
    ai_debt_sum: float
    ai_debt_avg: float
    commits: int


@dataclass
class PRMetrics:
    identifier: str  # 用 merge commit hash 或简短信息代替
    files_touched: int
    loc_added: int
    ai_debt_delta: float
    ai_risk_index: float
    top_files: List[str] = field(default_factory=list)
