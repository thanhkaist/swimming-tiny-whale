"""Persistence of the local high score, leaderboards, and player profile.

Deliberately tiny and dependency-free (JSON to files next to the game). All
failures degrade gracefully (zero high score / empty leaderboard / default
profile) so a missing or corrupt file never crashes the game. Fully
unit-testable by pointing the ``path`` argument at a temp file.
"""

from __future__ import annotations

import json
import os

import config

# A single leaderboard entry is a ``{"name": str, "score": int}`` dict.
Entry = dict
# A player profile is a plain dict; see ``_default_profile()``.
Profile = dict


def _here() -> str:
    """Directory containing this module (where save files live)."""
    return os.path.dirname(os.path.abspath(__file__))


def _default_path() -> str:
    """Absolute path to the high-score file beside this module."""
    return os.path.join(_here(), config.HIGHSCORE_FILE)


def _default_leaderboard_path() -> str:
    """Absolute path to the Normal-mode leaderboard file beside this module."""
    return os.path.join(_here(), config.LEADERBOARD_FILE)


def _default_profile_path() -> str:
    """Absolute path to the player-profile file beside this module."""
    return os.path.join(_here(), config.PROFILE_FILE)


def _leaderboard_path(path: str | None, mode_id: str | None) -> str:
    """Resolve the leaderboard file for ``mode_id``.

    An explicit ``path`` always wins (used by tests). Otherwise Normal mode
    (or no mode) uses the default file; every other mode gets its own file.
    """
    if path is not None:
        return path
    if mode_id is None or mode_id == config.DEFAULT_MODE:
        return _default_leaderboard_path()
    return os.path.join(_here(), config.LEADERBOARD_FILE_TEMPLATE.format(mode=mode_id))


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


def load_leaderboard(path: str | None = None, mode_id: str | None = None) -> list[Entry]:
    """Return the stored leaderboard (sorted, trimmed), or [] if unavailable."""
    target = _leaderboard_path(path, mode_id)
    try:
        with open(target, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        entries = data.get("scores", []) if isinstance(data, dict) else data
        if not isinstance(entries, list):
            return []
        return _sorted_trimmed(entries)
    except (OSError, ValueError, json.JSONDecodeError, TypeError):
        return []


def save_leaderboard(
    entries: list[Entry], path: str | None = None, mode_id: str | None = None
) -> bool:
    """Persist ``entries`` (sorted/trimmed first). Return success flag."""
    target = _leaderboard_path(path, mode_id)
    try:
        with open(target, "w", encoding="utf-8") as handle:
            json.dump({"scores": _sorted_trimmed(entries)}, handle)
        return True
    except OSError:
        return False


def qualifies(score: int, path: str | None = None, mode_id: str | None = None) -> bool:
    """True if ``score`` (> 0) would earn a place on the leaderboard."""
    if score <= 0:
        return False
    board = load_leaderboard(path, mode_id)
    if len(board) < config.LEADERBOARD_SIZE:
        return True
    return score > board[-1]["score"]


def add_score(
    name: str, score: int, path: str | None = None, mode_id: str | None = None
) -> tuple[list[Entry], int]:
    """Insert a score, persist the board, and return ``(board, rank)``.

    ``rank`` is the 1-based position of the inserted entry, or -1 if the score
    did not make the (trimmed) board. On a tie, the new entry places *below*
    existing entries with the same score (they were there first).
    """
    score = int(score)
    board = load_leaderboard(path, mode_id)  # sorted, trimmed, all scores > 0
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
    save_leaderboard(new_board, path, mode_id)
    return new_board, rank


# --------------------------------------------------------------------------- #
# Player profile (coins, unlocks, selections, per-mode bests)
# --------------------------------------------------------------------------- #
def _default_profile() -> Profile:
    """A fresh profile with everything at its starting value."""
    return {
        "coins": 0,
        "unlocked": [config.DEFAULT_CHARACTER],
        "selected_character": config.DEFAULT_CHARACTER,
        "selected_mode": config.DEFAULT_MODE,
        "selected_trail": config.DEFAULT_TRAIL,
        "per_mode_highscores": {},
    }


def _coerce_profile(data: object) -> Profile:
    """Merge stored ``data`` onto defaults, dropping anything malformed.

    Missing keys are backfilled and wrong types are replaced, so an old or
    partially-written profile always loads into a usable shape.
    """
    profile = _default_profile()
    if not isinstance(data, dict):
        return profile

    if isinstance(data.get("coins"), int) and data["coins"] >= 0:
        profile["coins"] = data["coins"]
    if isinstance(data.get("unlocked"), list):
        unlocked = [str(c) for c in data["unlocked"] if isinstance(c, str)]
        if config.DEFAULT_CHARACTER not in unlocked:
            unlocked.insert(0, config.DEFAULT_CHARACTER)
        profile["unlocked"] = unlocked
    for key in ("selected_character", "selected_mode", "selected_trail"):
        if isinstance(data.get(key), str):
            profile[key] = data[key]
    if isinstance(data.get("per_mode_highscores"), dict):
        profile["per_mode_highscores"] = {
            str(k): int(v)
            for k, v in data["per_mode_highscores"].items()
            if isinstance(v, (int, float))
        }
    return profile


def load_profile(path: str | None = None) -> Profile:
    """Return the stored profile merged onto defaults (never raises)."""
    target = path or _default_profile_path()
    try:
        with open(target, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError, json.JSONDecodeError, TypeError):
        return _default_profile()
    return _coerce_profile(data)


def save_profile(profile: Profile, path: str | None = None) -> bool:
    """Persist ``profile`` (coerced to a valid shape). Return success flag."""
    target = path or _default_profile_path()
    try:
        with open(target, "w", encoding="utf-8") as handle:
            json.dump(_coerce_profile(profile), handle)
        return True
    except OSError:
        return False


def add_coins(amount: int, path: str | None = None) -> int:
    """Add ``amount`` (clamped ≥ 0) coins to the balance; return new total."""
    profile = load_profile(path)
    profile["coins"] = max(0, profile["coins"] + max(0, int(amount)))
    save_profile(profile, path)
    return profile["coins"]


def spend_coins(amount: int, path: str | None = None) -> bool:
    """Deduct ``amount`` coins if affordable. Return True on success."""
    amount = int(amount)
    profile = load_profile(path)
    if amount < 0 or profile["coins"] < amount:
        return False
    profile["coins"] -= amount
    save_profile(profile, path)
    return True


def unlock_character(char_id: str, path: str | None = None) -> bool:
    """Add ``char_id`` to the unlocked list. Return True if newly unlocked."""
    profile = load_profile(path)
    if char_id in profile["unlocked"]:
        return False
    profile["unlocked"].append(char_id)
    save_profile(profile, path)
    return True


def set_selected(key: str, value: str, path: str | None = None) -> bool:
    """Set a ``selected_*`` profile field. Return True on success."""
    if key not in ("selected_character", "selected_mode", "selected_trail"):
        return False
    profile = load_profile(path)
    profile[key] = value
    return save_profile(profile, path)


def record_mode_score(mode_id: str, score: int, path: str | None = None) -> bool:
    """Update the per-mode best if ``score`` beats it. Return True if new best."""
    profile = load_profile(path)
    bests = profile["per_mode_highscores"]
    previous = int(bests.get(mode_id, 0))
    if score <= previous:
        return False
    bests[mode_id] = int(score)
    save_profile(profile, path)
    return True
