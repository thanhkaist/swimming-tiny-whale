"""Tests for coin collectibles: scroll, collection, magnet, cull, determinism."""

from __future__ import annotations

import random

import config
from collectibles import Coin, CollectibleField
from whale import Whale


class _FakeEffects:
    """Minimal stand-in for the (Phase 5) effect manager."""

    def __init__(self, magnet: bool = False) -> None:
        self.magnet = magnet


def test_coin_scrolls_left() -> None:
    coin = Coin(300, 300)
    coin.update(speed=3.0, dt=1.0)
    assert coin.x == 297


def test_coin_offscreen_detection() -> None:
    coin = Coin(-config.COIN_RADIUS - 1, 300)
    assert coin.is_offscreen()


def test_whale_collects_overlapping_coin() -> None:
    field = CollectibleField(random.Random(1))
    field.items = [Coin(config.WHALE_START_X, 360)]
    whale = Whale(x=config.WHALE_START_X, y=360)
    coins, _ = field.update(speed=0.0, whale=whale, dt=1.0)
    assert coins == config.COIN_VALUE
    assert field.items == []  # collected coins are culled


def test_distant_coin_not_collected() -> None:
    field = CollectibleField(random.Random(1))
    field.items = [Coin(config.WHALE_START_X + 300, 360)]
    whale = Whale(x=config.WHALE_START_X, y=360)
    coins, _ = field.update(speed=0.0, whale=whale, dt=1.0)
    assert coins == 0
    assert len(field.items) == 1


def test_coin_scored_once_then_removed() -> None:
    field = CollectibleField(random.Random(1))
    field.items = [Coin(config.WHALE_START_X, 360)]
    whale = Whale(x=config.WHALE_START_X, y=360)
    total = 0
    for _ in range(5):
        c, _ = field.update(speed=0.0, whale=whale, dt=1.0)
        total += c
    assert total == config.COIN_VALUE  # counted exactly once


def test_magnet_pulls_coin_toward_whale() -> None:
    field = CollectibleField(random.Random(1))
    coin = Coin(config.WHALE_START_X + 120, 200)
    field.items = [coin]
    whale = Whale(x=config.WHALE_START_X, y=400)
    start_dist = abs(coin.x - whale.x) + abs(coin.y - whale.y)
    field.update(speed=0.0, whale=whale, dt=1.0, effects=_FakeEffects(magnet=True))
    end_dist = abs(coin.x - whale.x) + abs(coin.y - whale.y)
    assert end_dist < start_dist


def test_magnet_eventually_collects() -> None:
    field = CollectibleField(random.Random(1))
    field.items = [Coin(config.WHALE_START_X + 150, 300)]
    whale = Whale(x=config.WHALE_START_X, y=300)
    collected = 0
    for _ in range(120):
        c, _ = field.update(speed=0.0, whale=whale, dt=1.0, effects=_FakeEffects(magnet=True))
        collected += c
        if collected:
            break
    assert collected == config.COIN_VALUE


def test_spawns_over_time() -> None:
    field = CollectibleField(random.Random(3))
    whale = Whale(x=config.WHALE_START_X, y=99999)  # far away, never collects
    for _ in range(400):
        field.update(speed=2.6, whale=whale, dt=1.0)
    assert len(field.items) >= 1


def test_spawn_stream_is_deterministic() -> None:
    whale = Whale(x=config.WHALE_START_X, y=99999)
    a = CollectibleField(random.Random(42))
    b = CollectibleField(random.Random(42))
    for _ in range(300):
        a.update(speed=2.6, whale=whale, dt=1.0)
        b.update(speed=2.6, whale=whale, dt=1.0)
    assert [round(i.x, 2) for i in a.items] == [round(i.x, 2) for i in b.items]
    assert [round(i.y, 2) for i in a.items] == [round(i.y, 2) for i in b.items]


def test_coins_aim_at_gap_when_field_given() -> None:
    from obstacles import ObstacleField

    obstacles = ObstacleField(random.Random(5))
    field = CollectibleField(random.Random(5))
    whale = Whale(x=config.WHALE_START_X, y=99999)
    # Force an immediate spawn and check the coin lands within the playable band.
    field._spawn_cooldown = 0
    field.update(speed=2.6, whale=whale, obstacle_field=obstacles, dt=1.0)
    assert field.items
    for coin in field.items:
        assert config.WATER_SURFACE_Y < coin.y < config.SEABED_Y
