"""Tests for high-score persistence (save/load, corruption tolerance)."""

from __future__ import annotations

import os

import storage


def test_roundtrip(tmp_path) -> None:  # noqa: ANN001 - pytest fixture
    path = os.path.join(tmp_path, "hs.json")
    assert storage.save_highscore(42, path)
    assert storage.load_highscore(path) == 42


def test_missing_file_returns_zero(tmp_path) -> None:  # noqa: ANN001
    path = os.path.join(tmp_path, "does_not_exist.json")
    assert storage.load_highscore(path) == 0


def test_corrupt_file_returns_zero(tmp_path) -> None:  # noqa: ANN001
    path = os.path.join(tmp_path, "bad.json")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("}{ not json at all")
    assert storage.load_highscore(path) == 0


def test_negative_scores_are_clamped(tmp_path) -> None:  # noqa: ANN001
    path = os.path.join(tmp_path, "neg.json")
    storage.save_highscore(-5, path)
    assert storage.load_highscore(path) == 0


def test_overwrite_keeps_latest(tmp_path) -> None:  # noqa: ANN001
    path = os.path.join(tmp_path, "hs.json")
    storage.save_highscore(10, path)
    storage.save_highscore(25, path)
    assert storage.load_highscore(path) == 25
