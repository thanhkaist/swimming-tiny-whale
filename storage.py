"""Persistence of the local high score and top-scores leaderboard.

Deliberately tiny and dependency-free (JSON to files next to the game). All
failures degrade gracefully (zero high score / empty leaderboard) so a missing
or corrupt file never crashes the game. Fully unit-testable by pointing the
``path`` argument at a temp file.
"""

from __future__ import annotations

import json
import os

import config

# A single leaderboard entry is a ``{"name": str, "score": int}`` dict.
Entry = dict


def _default_path() -> str:
    """Absolute path to the high-score file beside this module."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, config.HIGHSCORE_FILE)


def _default_leaderboard_path() -> str:
    """Absolute path to the leaderboard file beside this module."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, config.LEADERBOARD_FILE)


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


# --------------------------------------------------------------------------- #
# Leaderboard
# --------------------------------------------------------------------------- #
def _sanitise_name(name: str) -> str:
    """Uppercase, strip to A-Z0-9, and clamp to the initials length."""
    cleaned = "".join(c for c in str(name).upper() if c.isalnum())
    cleaned = cleaned[: config.INITIALS_LENGTH]
    return cleaned or config.DEFAULT_INITIALS


def _sorted_trimmed(entries: list[Entry]) -> list[Entry]:
    """Return entries sorted by score (desc) and trimmed to the max size."""
    clean: list[Entry] = []
    for e in entries:
        try:
            score = int(e["score"])
        except (KeyError, ValueError, TypeError):
            continue
        if score <= 0:
            continue
        clean.append({"name": _sanitise_name(e.get("name", "")), "score": score})
    # Stable sort keeps earlier (older) entries ahead on a score tie.
    clean.sort(key=lambda e: e["score"], reverse=True)
    return clean[: config.LEADERBOARD_SIZE]


def load_leaderboard(path: str | None = None) -> list[Entry]:
    """Return the stored leaderboard (sorted, trimmed), or [] if unavailable."""
    target = path or _default_leaderboard_path()
    try:
        with open(target, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        entries = data.get("scores", []) if isinstance(data, dict) else data
        if not isinstance(entries, list):
            return []
        return _sorted_trimmed(entries)
    except (OSError, ValueError, json.JSONDecodeError, TypeError):
        return []


def save_leaderboard(entries: list[Entry], path: str | None = None) -> bool:
    """Persist ``entries`` (sorted/trimmed first). Return success flag."""
    target = path or _default_leaderboard_path()
    try:
        with open(target, "w", encoding="utf-8") as handle:
            json.dump({"scores": _sorted_trimmed(entries)}, handle)
        return True
    except OSError:
        return False


def qualifies(score: int, path: str | None = None) -> bool:
    """True if ``score`` (> 0) would earn a place on the leaderboard."""
    if score <= 0:
        return False
    board = load_leaderboard(path)
    if len(board) < config.LEADERBOARD_SIZE:
        return True
    return score > board[-1]["score"]


def add_score(name: str, score: int, path: str | None = None) -> tuple[list[Entry], int]:
    """Insert a score, persist the board, and return ``(board, rank)``.

    ``rank`` is the 1-based position of the inserted entry, or -1 if the score
    did not make the (trimmed) board. On a tie, the new entry places *below*
    existing entries with the same score (they were there first).
    """
    score = int(score)
    board = load_leaderboard(path)  # already sorted, trimmed, all scores > 0
    entry: Entry = {"name": _sanitise_name(name), "score": score}

    # The new entry sorts below every existing entry with a >= score, so its
    # 0-based position is (#strictly-greater) + (#equal already present).
    if score > 0:
        position = sum(1 for e in board if e["score"] >= score)
        rank = position + 1 if position < config.LEADERBOARD_SIZE else -1
    else:
        rank = -1

    # Append last so the stable sort keeps it after equal-score existing entries.
    new_board = _sorted_trimmed(board + [entry])
    save_leaderboard(new_board, path)
    return new_board, rank
