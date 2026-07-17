"""Headless integration tests for the Game state machine and death handling.

These construct the full ``Game`` under the dummy SDL drivers and drive it with
synthetic events, verifying state transitions, scoring wiring, and game-over
without ever opening a window.
"""

from __future__ import annotations

import pygame

import config
from main import Game


def _press_space() -> None:
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))


def _advance(game: Game, frames: int) -> None:
    for _ in range(frames):
        game.handle_events()
        game.update(dt=1.0)


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
