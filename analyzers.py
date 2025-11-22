# analyzers.py
# Author: Cody
import ast
from pathlib import Path
from typing import Dict
from models import FileMetrics
from smells import analyze_smells


def safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        try:
            return path.read_text(encoding="latin-1")
        except Exception:
            return ""


def count_loc(source: str) -> int:
    return sum(1 for line in source.splitlines() if line.strip())


def compute_ai_influence(
    file_path: Path, file_git_stats: Dict[str, int], global_max_added: int
) -> float:
    """AI 影响度（MVP 版本）
    主要来自：最近新增行数 / 全局 max + 是否存在 AI-smell
    """
    added = file_git_stats.get("added", 0)
    if global_max_added <= 0:
        base = 0.0
    else:
        base = min(1.0, added / global_max_added)
    return base


def compute_ai_debt_score(smells, loc: int) -> float:
    if loc == 0:
        return 0.0
    # 按 smell 数量 / loc 做一个简单得分
    weight_dup = 3.0
    weight_api = 2.5
    weight_oe = 1.5
    weight_abs = 1.2
    weight_sf = 2.0

    score_raw = (
        smells.duplicate_blocks * weight_dup
        + smells.api_hallucinations * weight_api
        + smells.over_engineering * weight_oe
        + smells.unnecessary_abstractions * weight_abs
        + smells.silent_failures * weight_sf
    )
    # 归一化：每 100 行代码最多 10 分
    score = min(10.0, score_raw / max(loc / 100.0, 1.0))
    # 映射到 0–1
    return score / 10.0


def analyze_file(
    root: Path,
    relative_path: str,
    git_stats: Dict[str, int],
    global_max_added: int,
) -> FileMetrics:
    full_path = root / relative_path
    src = safe_read_text(full_path)
    loc = count_loc(src)
    try:
        tree = ast.parse(src)
    except SyntaxError:
        # 非 Python 或损坏文件，跳过 AST 分析
        return FileMetrics(
            path=relative_path,
            language="python",
            loc=loc,
            ai_influence_score=0.0,
            ai_debt_score=0.0,
            smells=analyze_smells(ast.parse(""), ""),
        )
    smells = analyze_smells(tree, src)

    ai_influence = compute_ai_influence(full_path, git_stats, global_max_added)
    ai_debt = compute_ai_debt_score(smells, loc)

    return FileMetrics(
        path=relative_path,
        language="python",
        loc=loc,
        ai_influence_score=ai_influence,
        ai_debt_score=ai_debt,
        smells=smells,
        recent_loc_added=git_stats.get("added", 0),
        total_loc_added=git_stats.get("added", 0),
    )
