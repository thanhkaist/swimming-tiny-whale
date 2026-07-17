"""Tests for the shop: buying characters/trails, equip, and insufficient funds."""

from __future__ import annotations

import pytest

import pygame

import config
import storage
from main import Game


@pytest.fixture()
def temp_storage(tmp_path, monkeypatch):  # noqa: ANN001 - pytest fixtures
    """Point every persistence path at throwaway temp files."""
    monkeypatch.setattr(storage, "_default_path", lambda: str(tmp_path / "hs.json"))
    monkeypatch.setattr(storage, "_default_leaderboard_path",
                        lambda: str(tmp_path / "lb.json"))
    monkeypatch.setattr(storage, "_default_profile_path",
                        lambda: str(tmp_path / "profile.json"))
    monkeypatch.setattr(storage, "_here", lambda: str(tmp_path))
    return tmp_path


def _open_shop(game: Game) -> None:
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_s))
    for _ in range(30):
        game.handle_events()
        game.update(dt=1.0)


def _index_of(game: Game, kind: str, item_id: str) -> int:
    for i, item in enumerate(game.shop_items):
        if item["kind"] == kind and item["id"] == item_id:
            return i
    raise AssertionError(f"{kind}:{item_id} not in shop")


def test_buy_character_with_enough_coins(temp_storage) -> None:  # noqa: ANN001
    storage.add_coins(500)
    game = Game()
    _open_shop(game)
    game.menu_index = _index_of(game, "char", "orca")
    game._confirm_shop()
    prof = storage.load_profile()
    assert "orca" in prof["unlocked"]
    assert prof["coins"] == 500 - config.CHAR_ORCA_COST
    # Purchased character leaves the shop list.
    assert all(not (it["kind"] == "char" and it["id"] == "orca") for it in game.shop_items)


def test_buy_character_insufficient_is_noop(temp_storage) -> None:  # noqa: ANN001
    storage.add_coins(10)  # not enough for anything
    game = Game()
    _open_shop(game)
    game.menu_index = _index_of(game, "char", "pip")
    game._confirm_shop()
    prof = storage.load_profile()
    assert "pip" not in prof["unlocked"]
    assert prof["coins"] == 10  # nothing spent


def test_buy_and_equip_trail(temp_storage) -> None:  # noqa: ANN001
    storage.add_coins(500)
    game = Game()
    _open_shop(game)
    game.menu_index = _index_of(game, "trail", "rainbow")
    game._confirm_shop()
    prof = storage.load_profile()
    assert "rainbow" in prof["unlocked_trails"]
    assert prof["selected_trail"] == "rainbow"        # auto-equipped on buy
    assert prof["coins"] == 500 - config.TRAIL_RAINBOW_COST


def test_equip_owned_trail_costs_nothing(temp_storage) -> None:  # noqa: ANN001
    storage.add_coins(500)
    storage.unlock_trail("bubbles")
    game = Game()
    _open_shop(game)
    game.menu_index = _index_of(game, "trail", "bubbles")
    game._confirm_shop()
    prof = storage.load_profile()
    assert prof["selected_trail"] == "bubbles"
    assert prof["coins"] == 500  # equipping an owned trail is free


def test_selected_trail_emits_particles(temp_storage) -> None:  # noqa: ANN001
    game = Game()
    game.profile["selected_trail"] = "rainbow"
    game.start_run()
    game.state = config.STATE_PLAYING
    game._started = True
    for _ in range(30):
        game.update(dt=1.0)
    assert len(game.particles.trail_bits) > 0


def test_none_trail_emits_nothing(temp_storage) -> None:  # noqa: ANN001
    game = Game()
    game.profile["selected_trail"] = "none"
    game.start_run()
    game.state = config.STATE_PLAYING
    game._started = True
    for _ in range(30):
        game.update(dt=1.0)
    assert len(game.particles.trail_bits) == 0
