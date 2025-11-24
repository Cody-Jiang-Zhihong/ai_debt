# scanner.py (v3 - file-level hashing + persistent cache)
# Author: Cody

from __future__ import annotations
import hashlib
import pickle
from pathlib import Path
from typing import List, Dict

from models import FileMetrics
from analyzers import analyze_file

CACHE_DIR = Path(".ai_debt_cache_scan")
CACHE_DIR.mkdir(exist_ok=True)


def _hash_file(path: Path) -> str:
    """Compute SHA256 of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _hash_snapshot(py_files: List[Path]) -> str:
    """
    Compute a stable 'snapshot hash' representing all Python files in the repo.

    If all file hashes are identical to a previous snapshot → we reuse the cached result.
    """
    file_hashes = []
    for f in py_files:
        try:
            fh = _hash_file(f)
            file_hashes.append(f"{f}:{fh}")
        except Exception:
            continue

    # stable order
    file_hashes.sort()
    full = "\n".join(file_hashes).encode("utf-8")
    return hashlib.sha256(full).hexdigest()


def _load_cache(snapshot_hash: str):
    cache_path = CACHE_DIR / f"{snapshot_hash}.pkl"
    if cache_path.exists():
        try:
            with open(cache_path, "rb") as f:
                return pickle.load(f)
        except Exception:
            return None
    return None


def _save_cache(snapshot_hash: str, data):
    cache_path = CACHE_DIR / f"{snapshot_hash}.pkl"
    try:
        with open(cache_path, "wb") as f:
            pickle.dump(data, f)
    except Exception:
        pass


def scan_repo(root: Path) -> List[FileMetrics]:
    """
    Optimized scan:
      • Compute SHA256 for every Python file
      • Compute snapshot hash
      • If snapshot hash cached => return cached
      • Otherwise run analyzers & save cache
    """
    root = Path(root)

    py_files = [
        f for f in root.rglob("*.py")
        if f.is_file() and ".git" not in f.parts
    ]

    # Compute deterministic snapshot fingerprint
    snapshot_hash = _hash_snapshot(py_files)

    # 1) try load old result
    cached = _load_cache(snapshot_hash)
    if cached is not None:
        return cached

    # 2) Otherwise fresh scan
    results = []
    for f in py_files:
        fm = analyze_file(str(f), rel_path=str(f.relative_to(root)),
                          stats=None, max_added=0)
        results.append(fm)

    # 3) Save to cache
    _save_cache(snapshot_hash, results)

    return results
