"""Tests for the player profile: coins, unlocks, selections, per-mode bests,
plus per-mode leaderboard filename isolation."""

from __future__ import annotations

import json
import os

import config
import storage


def _path(tmp_path) -> str:  # noqa: ANN001 - pytest fixture
    return os.path.join(tmp_path, "profile.json")


def test_default_profile_when_missing(tmp_path) -> None:  # noqa: ANN001
    p = storage.load_profile(_path(tmp_path))
    assert p["coins"] == 0
    assert p["unlocked"] == [config.DEFAULT_CHARACTER]
    assert p["selected_character"] == config.DEFAULT_CHARACTER
    assert p["selected_mode"] == config.DEFAULT_MODE


def test_roundtrip(tmp_path) -> None:  # noqa: ANN001
    path = _path(tmp_path)
    prof = storage.load_profile(path)
    prof["coins"] = 55
    prof["selected_mode"] = "hard"
    assert storage.save_profile(prof, path)
    reloaded = storage.load_profile(path)
    assert reloaded["coins"] == 55
    assert reloaded["selected_mode"] == "hard"


def test_corrupt_file_returns_default(tmp_path) -> None:  # noqa: ANN001
    path = _path(tmp_path)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("not json ]{")
    assert storage.load_profile(path)["coins"] == 0


def test_partial_profile_backfilled(tmp_path) -> None:  # noqa: ANN001
    path = _path(tmp_path)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"coins": 12}, handle)  # missing everything else
    p = storage.load_profile(path)
    assert p["coins"] == 12
    assert p["unlocked"] == [config.DEFAULT_CHARACTER]  # backfilled
    assert p["selected_character"] == config.DEFAULT_CHARACTER


def test_default_character_always_unlocked(tmp_path) -> None:  # noqa: ANN001
    path = _path(tmp_path)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"unlocked": ["heavy"]}, handle)  # default missing
    assert config.DEFAULT_CHARACTER in storage.load_profile(path)["unlocked"]


def test_add_coins(tmp_path) -> None:  # noqa: ANN001
    path = _path(tmp_path)
    assert storage.add_coins(10, path) == 10
    assert storage.add_coins(5, path) == 15
    assert storage.load_profile(path)["coins"] == 15


def test_add_coins_ignores_negative(tmp_path) -> None:  # noqa: ANN001
    path = _path(tmp_path)
    storage.add_coins(10, path)
    assert storage.add_coins(-100, path) == 10  # no change


def test_spend_coins_success_and_failure(tmp_path) -> None:  # noqa: ANN001
    path = _path(tmp_path)
    storage.add_coins(20, path)
    assert storage.spend_coins(15, path)
    assert storage.load_profile(path)["coins"] == 5
    assert not storage.spend_coins(10, path)  # insufficient
    assert storage.load_profile(path)["coins"] == 5  # unchanged


def test_unlock_character_idempotent(tmp_path) -> None:  # noqa: ANN001
    path = _path(tmp_path)
    assert storage.unlock_character("heavy", path)      # newly unlocked
    assert not storage.unlock_character("heavy", path)  # already owned
    assert "heavy" in storage.load_profile(path)["unlocked"]


def test_set_selected(tmp_path) -> None:  # noqa: ANN001
    path = _path(tmp_path)
    assert storage.set_selected("selected_character", "heavy", path)
    assert storage.load_profile(path)["selected_character"] == "heavy"
    assert not storage.set_selected("bogus_key", "x", path)  # rejected


def test_record_mode_score_new_best(tmp_path) -> None:  # noqa: ANN001
    path = _path(tmp_path)
    assert storage.record_mode_score("hard", 10, path)       # first is best
    assert not storage.record_mode_score("hard", 8, path)    # not better
    assert storage.record_mode_score("hard", 15, path)       # new best
    assert storage.load_profile(path)["per_mode_highscores"]["hard"] == 15


# --------------------------------------------------------------------------- #
# Per-mode leaderboard filename isolation
# --------------------------------------------------------------------------- #
def test_per_mode_leaderboards_are_isolated(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(storage, "_here", lambda: str(tmp_path))
    storage.add_score("NOR", 10, mode_id="normal")
    storage.add_score("HRD", 99, mode_id="hard")
    # Normal and Hard boards must not bleed into each other.
    assert [e["name"] for e in storage.load_leaderboard(mode_id="normal")] == ["NOR"]
    assert [e["name"] for e in storage.load_leaderboard(mode_id="hard")] == ["HRD"]
    # Normal mode shares the canonical default file.
    assert os.path.exists(os.path.join(tmp_path, config.LEADERBOARD_FILE))
    assert os.path.exists(os.path.join(
        tmp_path, config.LEADERBOARD_FILE_TEMPLATE.format(mode="hard")))
