"""Tests for whale characters: default neutrality, feel deltas, locking."""

from __future__ import annotations

import config
import characters
from whale import Whale


def test_registry_and_default() -> None:
    ids = {c.id for c in characters.CHARACTERS}
    assert config.DEFAULT_CHARACTER in ids
    assert characters.default().id == config.DEFAULT_CHARACTER
    assert characters.by_id("nope").id == config.DEFAULT_CHARACTER


def test_default_character_is_neutral() -> None:
    spec = characters.default()
    assert spec.gravity_scale == 1.0
    assert spec.impulse_scale == 1.0
    assert spec.hitbox_scale == 1.0
    assert spec.unlock_cost == 0
    assert spec.unlocked_by_default


def test_default_whale_physics_unchanged() -> None:
    # A default whale must fall exactly like the pre-character whale.
    plain = Whale(y=300)
    plain.update(dt=1.0)
    assert plain.vy == config.GRAVITY
    assert plain.y == 300 + config.GRAVITY


def test_default_whale_rect_identical() -> None:
    whale = Whale(x=100, y=200)
    r = whale.rect
    assert r.width == config.WHALE_WIDTH - config.WHALE_HITBOX_SHRINK_X
    assert r.height == config.WHALE_HEIGHT - config.WHALE_HITBOX_SHRINK_Y


def test_heavy_falls_faster_than_floaty() -> None:
    heavy = Whale(y=300, spec=characters.by_id("orca"))
    floaty = Whale(y=300, spec=characters.by_id("coral"))
    for _ in range(20):
        heavy.update(dt=1.0)
        floaty.update(dt=1.0)
    assert heavy.y > floaty.y  # orca sinks faster than coral


def test_swim_impulse_scales_with_character() -> None:
    heavy = Whale(y=300, spec=characters.by_id("orca"))
    heavy.swim()
    assert heavy.vy == config.SWIM_IMPULSE * characters.by_id("orca").impulse_scale


def test_tiny_has_smaller_hitbox() -> None:
    classic = Whale(x=100, y=200)
    tiny = Whale(x=100, y=200, spec=characters.by_id("pip"))
    assert tiny.rect.width < classic.rect.width
    assert tiny.rect.height < classic.rect.height


def test_non_default_characters_locked_by_default() -> None:
    for spec in characters.CHARACTERS:
        if spec.id != config.DEFAULT_CHARACTER:
            assert not spec.unlocked_by_default
            assert spec.unlock_cost > 0
