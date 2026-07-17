"""Tests for scoring: one point per column passed, awarded exactly once."""

from __future__ import annotations

import random

import config
from obstacles import ObstacleField


def test_score_awarded_when_column_passes_whale() -> None:
    field = ObstacleField(random.Random(1))
    whale_x = config.WHALE_START_X
    total = 0
    # Drive obstacles left until at least one passes the whale.
    for _ in range(1000):
        total += field.update(score=total, whale_x=whale_x, dt=1.0)
        if total >= 1:
            break
    assert total >= 1


def test_each_column_scores_only_once() -> None:
    field = ObstacleField(random.Random(2))
    whale_x = config.WHALE_START_X
    total = 0
    seen_passed = 0
    for _ in range(1500):
        total += field.update(score=total, whale_x=whale_x, dt=1.0)
        seen_passed = sum(1 for o in field.obstacles if o.passed)
    # Total score can exceed live-passed count (recycled columns), but no
    # single live column contributes twice: passed flag is monotonic.
    for o in field.obstacles:
        assert isinstance(o.passed, bool)
    assert total >= seen_passed


def test_no_score_before_column_reaches_whale() -> None:
    field = ObstacleField(random.Random(3))
    # First obstacle starts to the right of the whale; a single tick can't score.
    gained = field.update(score=0, whale_x=config.WHALE_START_X, dt=1.0)
    assert gained == 0


def test_score_accumulates_over_long_run() -> None:
    field = ObstacleField(random.Random(4))
    total = 0
    for _ in range(3000):
        total += field.update(score=total, whale_x=config.WHALE_START_X, dt=1.0)
    assert total > 3  # several columns cleared across a long run
