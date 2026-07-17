"""Tests for hazards: oscillating columns, jellyfish/mines, current zones."""

from __future__ import annotations

import random

import config
import modes
from hazards import CurrentZone, HazardField, Jellyfish, Mine
from obstacles import Obstacle, ObstacleField
from whale import Whale


# --- Oscillating columns --------------------------------------------------- #
def test_static_obstacle_gap_is_constant() -> None:
    obs = Obstacle(300, 360, 200, seed=1)  # default static
    obs.update(speed=3.0, dt=1.0)
    assert obs.gap_center == 360  # unchanged (only x moved)


def test_moving_obstacle_gap_oscillates() -> None:
    obs = Obstacle(300, 360, 160, seed=1, kind="moving", osc_amp=40, osc_speed=0.1)
    centers = set()
    for _ in range(80):
        obs.update(speed=0.0, dt=1.0)
        centers.add(round(obs.gap_center))
    assert len(centers) > 3  # actually moved through a range


def test_moving_gap_stays_within_band() -> None:
    field = ObstacleField(random.Random(9))
    # High score → moving columns are eligible; run long and step them.
    for _ in range(4000):
        field.update(score=25, whale_x=config.WHALE_START_X, dt=1.0)
    for obs in field.obstacles:
        assert obs.gap_top > config.WATER_SURFACE_Y
        assert obs.gap_bottom < config.SEABED_Y


def test_moving_columns_appear_at_high_score() -> None:
    field = ObstacleField(random.Random(2))
    kinds = set()
    for _ in range(5000):
        field.update(score=30, whale_x=config.WHALE_START_X, dt=1.0)
        kinds.update(o.kind for o in field.obstacles)
    assert "moving" in kinds


# --- Jellyfish / mines ----------------------------------------------------- #
def test_jellyfish_hit_returns_hit() -> None:
    field = HazardField(random.Random(1))
    field.hazards = [Jellyfish(config.WHALE_START_X, 300)]
    whale = Whale(x=config.WHALE_START_X, y=300)
    result = field.update(speed=0.0, whale=whale, dt=1.0)
    assert result == "hit"


def test_mine_hit_returns_hit() -> None:
    field = HazardField(random.Random(1))
    field.hazards = [Mine(config.WHALE_START_X, 300)]
    whale = Whale(x=config.WHALE_START_X, y=300)
    assert field.update(speed=0.0, whale=whale, dt=1.0) == "hit"


def test_no_hit_when_far() -> None:
    field = HazardField(random.Random(1))
    field.hazards = [Mine(config.WHALE_START_X + 300, 300)]
    whale = Whale(x=config.WHALE_START_X, y=300)
    assert field.update(speed=0.0, whale=whale, dt=1.0) is None


def test_current_zone_pushes_whale() -> None:
    field = HazardField(random.Random(1))
    whale = Whale(x=config.WHALE_START_X, y=300)
    # A downward current spanning the whale's position.
    field.currents = [CurrentZone(config.WHALE_START_X - 40, 260, config.CURRENT_PUSH)]
    before = whale.vy
    field.update(speed=0.0, whale=whale, dt=1.0)
    assert whale.vy > before  # pushed downward


def test_current_zone_no_push_when_outside() -> None:
    field = HazardField(random.Random(1))
    whale = Whale(x=config.WHALE_START_X, y=300)
    field.currents = [CurrentZone(config.WHALE_START_X + 300, 260, config.CURRENT_PUSH)]
    before = whale.vy
    field.update(speed=0.0, whale=whale, dt=1.0)
    assert whale.vy == before


def test_no_spawn_below_min_score() -> None:
    field = HazardField(random.Random(3))
    whale = Whale(x=config.WHALE_START_X, y=-9999)  # never collides
    for _ in range(600):
        field.update(speed=2.6, whale=whale, dt=1.0, score=0)
    assert not field.hazards and not field.currents


def test_spawns_at_high_score() -> None:
    field = HazardField(random.Random(3))
    whale = Whale(x=config.WHALE_START_X, y=-9999)
    for _ in range(1200):
        field.update(speed=2.6, whale=whale, dt=1.0, score=20)
    assert field.hazards or field.currents


def test_hazard_stream_deterministic() -> None:
    whale = Whale(x=config.WHALE_START_X, y=-9999)
    a = HazardField(random.Random(42), mode=modes.by_id("daily"))
    b = HazardField(random.Random(42), mode=modes.by_id("daily"))
    for _ in range(1500):
        a.update(speed=2.6, whale=whale, dt=1.0, score=20)
        b.update(speed=2.6, whale=whale, dt=1.0, score=20)
    assert [round(h.x, 2) for h in a.hazards] == [round(h.x, 2) for h in b.hazards]
    assert len(a.currents) == len(b.currents)
