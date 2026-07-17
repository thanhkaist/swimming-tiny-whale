"""Headless integration tests for the Game state machine and death handling.

These construct the full ``Game`` under the dummy SDL drivers and drive it with
synthetic events, verifying state transitions, scoring wiring, and game-over
without ever opening a window.
"""

from __future__ import annotations

import pytest

import pygame

import config
import storage
from main import Game


def _press_space() -> None:
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))


def _press_key(key: int, unicode: str = "") -> None:
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode))


def _advance(game: Game, frames: int) -> None:
    for _ in range(frames):
        game.handle_events()
        game.update(dt=1.0)


@pytest.fixture()
def temp_storage(tmp_path, monkeypatch):  # noqa: ANN001 - pytest fixtures
    """Point high-score and leaderboard persistence at throwaway temp files."""
    monkeypatch.setattr(storage, "_default_path", lambda: str(tmp_path / "hs.json"))
    monkeypatch.setattr(storage, "_default_leaderboard_path",
                        lambda: str(tmp_path / "lb.json"))
    monkeypatch.setattr(storage, "_default_profile_path",
                        lambda: str(tmp_path / "profile.json"))
    monkeypatch.setattr(storage, "_here", lambda: str(tmp_path))
    return tmp_path


def test_starts_on_title() -> None:
    game = Game()
    assert game.state == config.STATE_TITLE


def test_title_to_playing_transition() -> None:
    game = Game()
    _press_space()
    _advance(game, 30)  # allow the fade to complete
    assert game.state == config.STATE_PLAYING


def test_swim_raises_whale_during_play() -> None:
    game = Game()
    _press_space()
    _advance(game, 30)
    assert game.state == config.STATE_PLAYING
    # First flap begins the run; whale should get upward velocity.
    _press_space()
    game.handle_events()
    assert game._started
    assert game.whale.vy < 0


def test_collision_with_bounds_ends_run() -> None:
    game = Game()
    _press_space()
    _advance(game, 30)
    assert game.state == config.STATE_PLAYING
    # Start the run, then force the whale into the seabed.
    _press_space()
    game.handle_events()
    game.whale.y = config.SEABED_Y + 50
    game.update(dt=1.0)
    assert game.state == config.STATE_GAMEOVER


def test_death_triggers_juice_and_particles() -> None:
    game = Game()
    game.state = config.STATE_PLAYING
    game._started = True
    game.whale.y = config.SEABED_Y + 50
    game.update(dt=1.0)
    assert game.shake > 0
    assert game.flash > 0
    assert len(game.particles.splashes) > 0


def test_high_score_persists_on_new_best(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    import storage

    path = str(tmp_path / "hs.json")
    monkeypatch.setattr(storage, "_default_path", lambda: path)

    game = Game()
    game.highscore = 0
    game.state = config.STATE_PLAYING
    game._started = True
    game.score = 7
    game.whale.y = config.SEABED_Y + 50
    game.update(dt=1.0)
    assert game.state == config.STATE_GAMEOVER
    assert game.new_best
    assert storage.load_highscore(path) == 7


def test_gameover_to_restart() -> None:
    game = Game()
    game.state = config.STATE_GAMEOVER
    game.state_time = 60  # past the restart lockout
    _press_space()
    _advance(game, 40)
    assert game.state == config.STATE_PLAYING


def test_bounded_run_exits() -> None:
    game = Game()
    game.run(max_frames=20)  # must return, not hang
    assert True


# --------------------------------------------------------------------------- #
# Leaderboard + name entry
# --------------------------------------------------------------------------- #
def test_qualifying_death_starts_name_entry(temp_storage) -> None:  # noqa: ANN001
    game = Game()
    game.state = config.STATE_PLAYING
    game._started = True
    game.score = 5
    game.whale.y = config.SEABED_Y + 50
    game.update(dt=1.0)
    assert game.state == config.STATE_GAMEOVER
    assert game.name_entry_active


def test_zero_score_death_skips_name_entry(temp_storage) -> None:  # noqa: ANN001
    game = Game()
    game.state = config.STATE_PLAYING
    game._started = True
    game.score = 0
    game.whale.y = config.SEABED_Y + 50
    game.update(dt=1.0)
    assert game.state == config.STATE_GAMEOVER
    assert not game.name_entry_active


def test_typing_and_submitting_initials(temp_storage) -> None:  # noqa: ANN001
    game = Game()
    game.state = config.STATE_PLAYING
    game._started = True
    game.score = 8
    game.whale.y = config.SEABED_Y + 50
    game.update(dt=1.0)
    assert game.name_entry_active

    for key, ch in ((pygame.K_a, "a"), (pygame.K_b, "b"), (pygame.K_c, "c")):
        _press_key(key, ch)
        game.handle_events()
    assert game.entry_initials == "ABC"

    _press_key(pygame.K_BACKSPACE)
    game.handle_events()
    assert game.entry_initials == "AB"

    _press_key(pygame.K_RETURN)
    game.handle_events()
    assert not game.name_entry_active
    assert game.entry_rank == 1
    board = storage.load_leaderboard()
    assert board[0] == {"name": "AB", "score": 8}


def test_initials_capped_at_length(temp_storage) -> None:  # noqa: ANN001
    game = Game()
    game.name_entry_active = True
    game.entry_initials = ""
    for key, ch in ((pygame.K_a, "a"), (pygame.K_b, "b"), (pygame.K_c, "c"), (pygame.K_d, "d")):
        _press_key(key, ch)
        game.handle_events()
    assert game.entry_initials == "ABC"  # 4th char ignored


def test_space_during_name_entry_does_not_restart(temp_storage) -> None:  # noqa: ANN001
    game = Game()
    game.state = config.STATE_GAMEOVER
    game.name_entry_active = True
    game.state_time = 60
    _press_space()
    _advance(game, 30)
    assert game.state == config.STATE_GAMEOVER  # still entering, no restart


def test_open_and_leave_leaderboard_from_title(temp_storage) -> None:  # noqa: ANN001
    game = Game()
    assert game.state == config.STATE_TITLE
    _press_key(pygame.K_l)
    _advance(game, 30)
    assert game.state == config.STATE_LEADERBOARD
    _press_space()
    _advance(game, 30)
    assert game.state == config.STATE_TITLE  # returns to opener


def test_leaderboard_returns_to_gameover(temp_storage) -> None:  # noqa: ANN001
    game = Game()
    game.state = config.STATE_GAMEOVER
    game.name_entry_active = False
    _press_key(pygame.K_l)
    _advance(game, 30)
    assert game.state == config.STATE_LEADERBOARD
    _press_space()
    _advance(game, 30)
    assert game.state == config.STATE_GAMEOVER


# --------------------------------------------------------------------------- #
# Game modes
# --------------------------------------------------------------------------- #
def test_open_mode_select_and_pick_hard(temp_storage) -> None:  # noqa: ANN001
    import modes

    game = Game()
    _press_key(pygame.K_d)                 # open mode select from title
    _advance(game, 30)
    assert game.state == config.STATE_MODESELECT
    # Move cursor to Hard and confirm.
    hard_index = [m.id for m in modes.MODES].index("hard")
    game.menu_index = hard_index
    _press_key(pygame.K_RETURN)
    _advance(game, 30)
    assert game.state == config.STATE_TITLE
    assert game.profile["selected_mode"] == "hard"
    assert game.run_mode.id == "hard"


def test_selected_mode_drives_live_field(temp_storage) -> None:  # noqa: ANN001
    game = Game()
    game.profile["selected_mode"] = "hard"
    game.start_run()
    assert game.field.mode.id == "hard"


def test_zen_mode_never_dies(temp_storage) -> None:  # noqa: ANN001
    game = Game()
    game.profile["selected_mode"] = "zen"
    game.start_run()
    game.state = config.STATE_PLAYING
    game._started = True
    # Slam the whale into the seabed repeatedly — Zen must keep playing.
    for _ in range(10):
        game.whale.y = config.SEABED_Y + 80
        game.update(dt=1.0)
    assert game.state == config.STATE_PLAYING
    assert game.whale.rect.bottom <= config.SEABED_Y + 1


def test_mode_best_recorded_on_death(temp_storage) -> None:  # noqa: ANN001
    import storage

    game = Game()
    game.profile["selected_mode"] = "hard"
    game.start_run()
    game.state = config.STATE_PLAYING
    game._started = True
    game.score = 9
    game.whale.y = config.SEABED_Y + 50
    game.update(dt=1.0)
    assert game.state == config.STATE_GAMEOVER
    assert storage.load_profile()["per_mode_highscores"]["hard"] == 9


# --------------------------------------------------------------------------- #
# Coins
# --------------------------------------------------------------------------- #
def test_collected_coins_bank_on_death(temp_storage) -> None:  # noqa: ANN001
    import storage
    from collectibles import Coin

    game = Game()
    game.start_run()
    game.state = config.STATE_PLAYING
    game._started = True
    # Drop a coin right on the whale so it is collected next tick.
    game.collectibles.items = [Coin(game.whale.x, game.whale.y)]
    game.update(dt=1.0)
    assert game.run_coins >= config.COIN_VALUE
    # Now die and confirm the coins are persisted to the profile.
    game.whale.y = config.SEABED_Y + 50
    game.update(dt=1.0)
    assert game.state == config.STATE_GAMEOVER
    assert storage.load_profile()["coins"] >= config.COIN_VALUE


def test_select_unlocked_character(temp_storage) -> None:  # noqa: ANN001
    import characters

    game = Game()
    game.profile["unlocked"] = ["classic", "orca"]
    _press_key(pygame.K_c)
    _advance(game, 30)
    assert game.state == config.STATE_CHARSELECT
    game.menu_index = [c.id for c in characters.CHARACTERS].index("orca")
    _press_key(pygame.K_RETURN)
    _advance(game, 30)
    assert game.state == config.STATE_TITLE
    assert game.profile["selected_character"] == "orca"
    assert game.whale.spec.id == "orca"


def test_cannot_select_locked_character(temp_storage) -> None:  # noqa: ANN001
    import characters

    game = Game()
    game.profile["unlocked"] = ["classic"]
    _press_key(pygame.K_c)
    _advance(game, 30)
    assert game.state == config.STATE_CHARSELECT
    game.menu_index = [c.id for c in characters.CHARACTERS].index("pip")
    _press_key(pygame.K_RETURN)
    _advance(game, 10)
    # Locked pick is rejected: stays on the select screen, selection unchanged.
    assert game.state == config.STATE_CHARSELECT
    assert game.profile["selected_character"] == "classic"


def test_coins_bank_on_quit_in_zen(temp_storage) -> None:  # noqa: ANN001
    import storage
    from collectibles import Coin

    game = Game()
    game.profile["selected_mode"] = "zen"
    game.start_run()
    game.state = config.STATE_PLAYING
    game._started = True
    game.collectibles.items = [Coin(game.whale.x, game.whale.y)]
    game.update(dt=1.0)
    banked = game.run_coins
    assert banked >= config.COIN_VALUE
    game._request_quit()  # Zen never dies; quitting must still bank coins
    assert not game.running
    assert storage.load_profile()["coins"] >= banked
