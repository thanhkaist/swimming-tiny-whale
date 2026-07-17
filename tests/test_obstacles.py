"""Tests for obstacle geometry, difficulty ramp, scrolling, and collision."""

from __future__ import annotations

import random

import pygame

import config
from obstacles import Obstacle, ObstacleField


def test_gap_geometry() -> None:
    obs = Obstacle(x=100, gap_center=300, gap_size=200, seed=1)
    assert obs.gap_top == 200
    assert obs.gap_bottom == 400
    assert obs.top_rect.bottom == 200
    assert obs.bottom_rect.top == 400


def test_collision_with_top_column() -> None:
    obs = Obstacle(x=100, gap_center=300, gap_size=160, seed=1)
    # A rect well above the gap overlaps the top column.
    rect = pygame.Rect(110, config.WATER_SURFACE_Y + 10, 30, 30)
    assert obs.collides_with(rect)


def test_no_collision_inside_gap() -> None:
    obs = Obstacle(x=100, gap_center=300, gap_size=200, seed=1)
    rect = pygame.Rect(110, 290, 30, 20)  # centred in the gap
    assert not obs.collides_with(rect)


def test_scrolling_moves_left() -> None:
    obs = Obstacle(x=300, gap_center=300, gap_size=200, seed=1)
    obs.update(speed=3.0, dt=1.0)
    assert obs.x == 297


def test_offscreen_detection() -> None:
    obs = Obstacle(x=-config.OBSTACLE_WIDTH - 1, gap_center=300, gap_size=200, seed=1)
    assert obs.is_offscreen()


def test_gap_shrinks_with_score() -> None:
    easy = ObstacleField.gap_for_score(0)
    hard = ObstacleField.gap_for_score(20)
    assert easy == config.OBSTACLE_GAP_START
    assert hard < easy
    assert hard >= config.OBSTACLE_GAP_MIN


def test_gap_never_below_minimum() -> None:
    assert ObstacleField.gap_for_score(10_000) == config.OBSTACLE_GAP_MIN


def test_speed_ramps_with_score() -> None:
    slow = ObstacleField.speed_for_score(0)
    fast = ObstacleField.speed_for_score(30)
    assert slow == config.OBSTACLE_SPEED_START
    assert fast > slow
    assert fast <= config.OBSTACLE_SPEED_MAX


def test_speed_capped_at_max() -> None:
    assert ObstacleField.speed_for_score(10_000) == config.OBSTACLE_SPEED_MAX


def test_field_spawns_first_obstacle() -> None:
    field = ObstacleField(random.Random(1))
    assert len(field.obstacles) == 1
    assert field.obstacles[0].x > config.SCREEN_WIDTH


def test_gaps_stay_within_playable_band() -> None:
    field = ObstacleField(random.Random(7))
    # Advance a long run and confirm every gap remains reachable.
    for _ in range(4000):
        field.update(score=5, whale_x=config.WHALE_START_X, dt=1.0)
    for obs in field.obstacles:
        assert obs.gap_top > config.WATER_SURFACE_Y
        assert obs.gap_bottom < config.SEABED_Y


def test_deterministic_with_seed() -> None:
    a = ObstacleField(random.Random(42))
    b = ObstacleField(random.Random(42))
    for _ in range(500):
        a.update(score=0, whale_x=config.WHALE_START_X, dt=1.0)
        b.update(score=0, whale_x=config.WHALE_START_X, dt=1.0)
    assert [round(o.gap_center, 3) for o in a.obstacles] == [
        round(o.gap_center, 3) for o in b.obstacles
    ]


def test_new_columns_appear_over_time() -> None:
    field = ObstacleField(random.Random(3))
    for _ in range(300):
        field.update(score=0, whale_x=config.WHALE_START_X, dt=1.0)
    assert len(field.obstacles) >= 2
