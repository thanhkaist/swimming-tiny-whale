"""Tests for power-up effects: timers, time-scale, shield, shrink, magnet."""

from __future__ import annotations

import random

import config
import powerups
from collectibles import CollectibleField, PowerUp
from whale import Whale


def test_activate_and_expire() -> None:
    em = powerups.EffectManager()
    em.activate(powerups.MAGNET)
    assert em.magnet
    for _ in range(int(config.MAGNET_DURATION) + 1):
        em.update(1.0)
    assert not em.magnet
    assert em.active == {}


def test_time_scale_only_while_slowmo() -> None:
    em = powerups.EffectManager()
    assert em.time_scale == 1.0
    em.activate(powerups.SLOWMO)
    assert em.time_scale == config.SLOWMO_TIME_SCALE
    for _ in range(int(config.SLOWMO_DURATION) + 1):
        em.update(1.0)
    assert em.time_scale == 1.0


def test_shield_consumed_once() -> None:
    em = powerups.EffectManager()
    em.activate(powerups.SHIELD)
    assert em.shield
    assert em.consume_shield() is True
    assert not em.shield
    assert em.consume_shield() is False  # already spent


def test_shrink_lowers_hitbox_scale() -> None:
    em = powerups.EffectManager()
    assert em.hitbox_scale == 1.0
    em.activate(powerups.SHRINK)
    assert em.hitbox_scale == config.SHRINK_HITBOX_SCALE


def test_shrink_shrinks_whale_rect() -> None:
    em = powerups.EffectManager()
    em.activate(powerups.SHRINK)
    whale = Whale(x=100, y=200)
    full = whale.rect.width
    whale.hitbox_scale = whale.spec.hitbox_scale * em.hitbox_scale
    assert whale.rect.width < full


def test_timer_uses_real_dt_not_scaled() -> None:
    # Slow-mo must not prolong itself: decrement by real dt each call.
    em = powerups.EffectManager()
    em.activate(powerups.SLOWMO)
    steps = 0
    while em.is_active(powerups.SLOWMO):
        em.update(1.0)  # real dt, even though the world would run at 0.5x
        steps += 1
    assert steps == int(config.SLOWMO_DURATION)


def test_hud_items_report_fractions() -> None:
    em = powerups.EffectManager()
    em.activate(powerups.MAGNET)
    (kind, color, frac), = em.hud_items()
    assert kind == powerups.MAGNET
    assert frac == 1.0
    em.update(config.MAGNET_DURATION / 2)
    assert abs(em.hud_items()[0][2] - 0.5) < 0.05


def test_powerup_collected_returns_kind() -> None:
    field = CollectibleField(random.Random(1))
    field.items = [PowerUp(config.WHALE_START_X, 300, powerups.SHIELD)]
    whale = Whale(x=config.WHALE_START_X, y=300)
    coins, kinds = field.update(speed=0.0, whale=whale, dt=1.0)
    assert coins == 0
    assert kinds == [powerups.SHIELD]


def test_magnet_effect_pulls_via_field() -> None:
    field = CollectibleField(random.Random(1))
    from collectibles import Coin

    field.items = [Coin(config.WHALE_START_X + 140, 250)]
    whale = Whale(x=config.WHALE_START_X, y=400)
    em = powerups.EffectManager()
    em.activate(powerups.MAGNET)
    start = abs(field.items[0].x - whale.x) + abs(field.items[0].y - whale.y)
    field.update(speed=0.0, whale=whale, dt=1.0, effects=em)
    if field.items:  # not yet collected
        end = abs(field.items[0].x - whale.x) + abs(field.items[0].y - whale.y)
        assert end < start
