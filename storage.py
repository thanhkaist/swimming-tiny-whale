"""Persistence of the local high score.

Deliberately tiny and dependency-free (JSON to a file next to the game). All
failures degrade to a zero high score so a missing/corrupt file never crashes
the game. Fully unit-testable by pointing ``path`` at a temp file.
"""

from __future__ import annotations

import json
import os

import config


def _default_path() -> str:
    """Absolute path to the high-score file beside this module."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, config.HIGHSCORE_FILE)


def load_highscore(path: str | None = None) -> int:
    """Return the stored high score, or 0 if unavailable/corrupt."""
    target = path or _default_path()
    try:
        with open(target, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        value = int(data.get("highscore", 0))
        return max(0, value)
    except (OSError, ValueError, json.JSONDecodeError, TypeError):
        return 0


def save_highscore(score: int, path: str | None = None) -> bool:
    """Persist ``score``. Return True on success, False on any I/O failure."""
    target = path or _default_path()
    try:
        with open(target, "w", encoding="utf-8") as handle:
            json.dump({"highscore": int(max(0, score))}, handle)
        return True
    except OSError:
        return False
