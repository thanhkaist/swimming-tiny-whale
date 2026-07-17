"""Tests for the leaderboard: insertion, ordering, ranking, trimming, safety."""

from __future__ import annotations

import json
import os

import config
import storage


def _path(tmp_path) -> str:  # noqa: ANN001 - pytest fixture
    return os.path.join(tmp_path, "lb.json")


def test_empty_leaderboard(tmp_path) -> None:  # noqa: ANN001
    assert storage.load_leaderboard(_path(tmp_path)) == []


def test_add_and_load(tmp_path) -> None:  # noqa: ANN001
    p = _path(tmp_path)
    storage.add_score("ABC", 10, p)
    board = storage.load_leaderboard(p)
    assert board == [{"name": "ABC", "score": 10}]


def test_sorted_descending(tmp_path) -> None:  # noqa: ANN001
    p = _path(tmp_path)
    for name, score in [("AAA", 5), ("BBB", 20), ("CCC", 12)]:
        storage.add_score(name, score, p)
    board = storage.load_leaderboard(p)
    assert [e["score"] for e in board] == [20, 12, 5]
    assert [e["name"] for e in board] == ["BBB", "CCC", "AAA"]


def test_rank_returned(tmp_path) -> None:  # noqa: ANN001
    p = _path(tmp_path)
    storage.add_score("AAA", 30, p)
    storage.add_score("BBB", 10, p)
    _, rank = storage.add_score("CCC", 20, p)
    assert rank == 2  # 20 sits between 30 and 10


def test_trimmed_to_size(tmp_path) -> None:  # noqa: ANN001
    p = _path(tmp_path)
    for i in range(config.LEADERBOARD_SIZE + 5):
        storage.add_score("AAA", i + 1, p)
    board = storage.load_leaderboard(p)
    assert len(board) == config.LEADERBOARD_SIZE
    # Only the top N scores survive.
    assert board[0]["score"] == config.LEADERBOARD_SIZE + 5
    assert board[-1]["score"] == 6


def test_low_score_off_full_board_gets_no_rank(tmp_path) -> None:  # noqa: ANN001
    p = _path(tmp_path)
    for i in range(config.LEADERBOARD_SIZE):
        storage.add_score("AAA", 100 + i, p)
    _, rank = storage.add_score("ZZZ", 1, p)
    assert rank == -1  # didn't make the full board


def test_tie_places_new_entry_below(tmp_path) -> None:  # noqa: ANN001
    p = _path(tmp_path)
    storage.add_score("OLD", 15, p)
    board, rank = storage.add_score("NEW", 15, p)
    assert rank == 2
    assert board[0]["name"] == "OLD"
    assert board[1]["name"] == "NEW"


def test_qualifies_on_empty_board(tmp_path) -> None:  # noqa: ANN001
    assert storage.qualifies(1, _path(tmp_path))


def test_zero_score_never_qualifies(tmp_path) -> None:  # noqa: ANN001
    assert not storage.qualifies(0, _path(tmp_path))


def test_qualifies_only_if_beats_lowest_when_full(tmp_path) -> None:  # noqa: ANN001
    p = _path(tmp_path)
    for i in range(config.LEADERBOARD_SIZE):
        storage.add_score("AAA", 50 + i, p)
    assert not storage.qualifies(50, p)   # equal to lowest is not enough
    assert storage.qualifies(60, p)       # beats the lowest


def test_name_sanitised(tmp_path) -> None:  # noqa: ANN001
    p = _path(tmp_path)
    storage.add_score("a b!c#d", 10, p)
    board = storage.load_leaderboard(p)
    assert board[0]["name"] == "ABC"  # uppercased, alnum only, clamped to 3


def test_empty_name_falls_back(tmp_path) -> None:  # noqa: ANN001
    p = _path(tmp_path)
    storage.add_score("", 10, p)
    board = storage.load_leaderboard(p)
    assert board[0]["name"] == config.DEFAULT_INITIALS


def test_corrupt_file_returns_empty(tmp_path) -> None:  # noqa: ANN001
    p = _path(tmp_path)
    with open(p, "w", encoding="utf-8") as handle:
        handle.write("not json {[")
    assert storage.load_leaderboard(p) == []


def test_ignores_nonpositive_and_malformed_entries(tmp_path) -> None:  # noqa: ANN001
    p = _path(tmp_path)
    with open(p, "w", encoding="utf-8") as handle:
        json.dump({"scores": [
            {"name": "WIN", "score": 12},
            {"name": "ZER", "score": 0},
            {"name": "NEG", "score": -4},
            {"name": "BAD", "score": "oops"},
            {"nope": True},
        ]}, handle)
    board = storage.load_leaderboard(p)
    assert board == [{"name": "WIN", "score": 12}]


def test_accepts_bare_list_format(tmp_path) -> None:  # noqa: ANN001
    p = _path(tmp_path)
    with open(p, "w", encoding="utf-8") as handle:
        json.dump([{"name": "XYZ", "score": 7}], handle)
    assert storage.load_leaderboard(p) == [{"name": "XYZ", "score": 7}]
