"""Tests for game modes: difficulty scaling, daily-seed determinism, Zen."""

from __future__ import annotations

import datetime
import random

import config
import modes
from obstacles import ObstacleField


def test_registry_has_expected_modes() -> None:
    ids = {m.id for m in modes.MODES}
    assert {"zen", "normal", "hard", "daily"} <= ids
    assert modes.default().id == config.DEFAULT_MODE


def test_by_id_falls_back_to_default() -> None:
    assert modes.by_id("nonexistent").id == config.DEFAULT_MODE
    assert modes.by_id(None).id == config.DEFAULT_MODE


def test_daily_seed_is_deterministic_per_date() -> None:
    d = datetime.date(2026, 7, 18)
    assert modes.daily_seed(d) == modes.daily_seed(d) == 20260718
    assert modes.daily_seed(datetime.date(2026, 7, 19)) != modes.daily_seed(d)


def test_daily_seed_reproduces_identical_run() -> None:
    seed = modes.daily_seed(datetime.date(2026, 7, 18))
    daily = modes.by_id("daily")
    a = ObstacleField(random.Random(seed), mode=daily)
    b = ObstacleField(random.Random(seed), mode=daily)
    for _ in range(400):
        a.update(0, config.WHALE_START_X, 1.0)
        b.update(0, config.WHALE_START_X, 1.0)
    assert [round(o.gap_center, 3) for o in a.obstacles] == \
           [round(o.gap_center, 3) for o in b.obstacles]


def test_gap_ordering_hard_lt_normal_lt_zen() -> None:
    score = 6
    hard = ObstacleField.gap_for_score(score, modes.by_id("hard"))
    normal = ObstacleField.gap_for_score(score, modes.by_id("normal"))
    zen = ObstacleField.gap_for_score(score, modes.by_id("zen"))
    assert hard < normal < zen


def test_normal_mode_matches_legacy_single_arg() -> None:
    # The mode-aware form with Normal must equal the old single-arg behavior.
    for score in (0, 5, 20, 10_000):
        assert ObstacleField.gap_for_score(score) == \
               ObstacleField.gap_for_score(score, modes.by_id("normal"))
        assert ObstacleField.speed_for_score(score) == \
               ObstacleField.speed_for_score(score, modes.by_id("normal"))


def test_hard_speed_exceeds_normal() -> None:
    assert ObstacleField.speed_for_score(0, modes.by_id("hard")) > \
           ObstacleField.speed_for_score(0, modes.by_id("normal"))


def test_zen_gap_never_below_its_floor() -> None:
    zen = modes.by_id("zen")
    assert ObstacleField.gap_for_score(10_000, zen) == config.MODE_ZEN_GAP_MIN


def test_mode_gaps_stay_within_band_over_long_run() -> None:
    for mode in modes.MODES:
        field = ObstacleField(random.Random(7), mode=mode)
        for _ in range(3000):
            field.update(score=8, whale_x=config.WHALE_START_X, dt=1.0)
        for obs in field.obstacles:
            assert obs.gap_top > config.WATER_SURFACE_Y
            assert obs.gap_bottom < config.SEABED_Y
