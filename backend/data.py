"""Data loading helpers for the simulator backend."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CACHE_PATH = DATA_DIR / "results_cache.json"
SNAPSHOT_PATH = DATA_DIR / "results_snapshot.json"


def _empty_dataset() -> dict[str, Any]:
    """Fallback dataset used when the cache is missing."""
    return {
        "season": "2025-26",
        "ucl": {"qualifying": {}, "league_phase": [], "knockout": {}},
        "uel": {"qualifying": {}, "league_phase": [], "knockout": {}},
        "uecl": {"qualifying": {}, "league_phase": [], "knockout": {}},
    }


def load_dataset() -> dict[str, Any]:
    """
    Load the current dataset snapshot.

    Prefers the locally scraped cache output if present (gitignored),
    otherwise falls back to a committed snapshot so the public repo works
    out-of-the-box.
    """
    if CACHE_PATH.exists():
        with CACHE_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    if SNAPSHOT_PATH.exists():
        with SNAPSHOT_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    return _empty_dataset()
