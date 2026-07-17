"""Physics tests for the whale: gravity, swim impulse, clamping, tilt, bounds."""

from __future__ import annotations

import config
from whale import Whale


def test_gravity_pulls_whale_down() -> None:
    whale = Whale(y=300)
    start_y = whale.y
    for _ in range(10):
        whale.update(dt=1.0)
    assert whale.y > start_y
    assert whale.vy > 0


def test_swim_gives_upward_velocity() -> None:
    whale = Whale(y=300)
    whale.swim()
    assert whale.vy == config.SWIM_IMPULSE
    assert whale.vy < 0


def test_swim_then_rises_before_falling() -> None:
    whale = Whale(y=300)
    start_y = whale.y
    whale.swim()
    whale.update(dt=1.0)
    assert whale.y < start_y  # moved up on the first frame after a flap


def test_fall_speed_is_clamped() -> None:
    whale = Whale(y=300)
    for _ in range(200):
        whale.update(dt=1.0)
    assert whale.vy <= config.MAX_FALL_SPEED


def test_rise_speed_is_clamped() -> None:
    whale = Whale(y=300)
    # Repeated flaps should never exceed the max rise speed.
    for _ in range(5):
        whale.swim()
        whale.update(dt=1.0)
    assert whale.vy >= config.MAX_RISE_SPEED


def test_no_gravity_when_disabled() -> None:
    whale = Whale(y=300)
    whale.update(dt=1.0, apply_gravity=False)
    assert whale.y == 300
    assert whale.vy == 0.0


def test_tilt_points_up_when_rising() -> None:
    whale = Whale(y=300)
    whale.swim()
    for _ in range(3):
        whale.update(dt=1.0)
    assert whale.tilt > 0  # positive degrees == nose up


def test_tilt_points_down_when_falling() -> None:
    whale = Whale(y=300)
    for _ in range(30):
        whale.update(dt=1.0)
    assert whale.tilt < 0


def test_hits_surface() -> None:
    whale = Whale(y=config.WATER_SURFACE_Y - 5)
    assert whale.hits_bounds()


def test_hits_seabed() -> None:
    whale = Whale(y=config.SEABED_Y + 5)
    assert whale.hits_bounds()


def test_mid_water_is_safe() -> None:
    whale = Whale(y=(config.WATER_SURFACE_Y + config.SEABED_Y) // 2)
    assert not whale.hits_bounds()


def test_reset_restores_start_state() -> None:
    whale = Whale(y=300)
    whale.swim()
    for _ in range(20):
        whale.update(dt=1.0)
    whale.reset()
    assert whale.y == config.WHALE_START_Y
    assert whale.vy == 0.0
    assert whale.alive


def test_frame_rate_independence() -> None:
    """Two half-steps should land close to one full step."""
    a = Whale(y=300)
    b = Whale(y=300)
    a.update(dt=1.0)
    b.update(dt=0.5)
    b.update(dt=0.5)
    assert abs(a.y - b.y) < 1.0
