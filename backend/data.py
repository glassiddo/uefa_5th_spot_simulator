"""Data loading helpers for the simulator backend."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CACHE_PATH = DATA_DIR / "results_cache.json"


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

    The current implementation reads the cached scrape output if present,
    and falls back to an empty shell so the API always responds cleanly.
    """
    if CACHE_PATH.exists():
        with CACHE_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    return _empty_dataset()

