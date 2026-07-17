"""Coral/seaweed obstacle columns: spawning, scrolling, scoring, collision.

All logic here is display-independent (pure geometry + a seeded RNG) so it can
be unit-tested headless. The paired top/bottom columns share a vertical gap the
whale must swim through. Difficulty ramps with the current score: the gap
tightens and the scroll speed increases, both clamped to sane limits.
"""

from __future__ import annotations

import random

import pygame

import config
import modes
from util import clamp


class Obstacle:
    """A single top+bottom coral column pair with a gap between them."""

    def __init__(self, x: float, gap_center: float, gap_size: float, seed: int) -> None:
        """Create a column pair.

        Args:
            x: Left edge x-position of the column.
            gap_center: Y-coordinate of the middle of the gap.
            gap_size: Vertical height of the passable gap.
            seed: Deterministic seed for this column's procedural art.
        """
        self.x: float = float(x)
        self.gap_center: float = float(gap_center)
        self.gap_size: float = float(gap_size)
        self.width: int = config.OBSTACLE_WIDTH
        self.seed: int = seed
        self.passed: bool = False

        # Lazily built art (top column hangs down, bottom column grows up).
        self._top_surface: pygame.Surface | None = None
        self._bottom_surface: pygame.Surface | None = None

    # ------------------------------------------------------------------ #
    # Geometry
    # ------------------------------------------------------------------ #
    @property
    def gap_top(self) -> float:
        """Y-coordinate of the top edge of the gap."""
        return self.gap_center - self.gap_size / 2

    @property
    def gap_bottom(self) -> float:
        """Y-coordinate of the bottom edge of the gap."""
        return self.gap_center + self.gap_size / 2

    @property
    def top_rect(self) -> pygame.Rect:
        """Collision rect for the upper column."""
        top = config.WATER_SURFACE_Y
        return pygame.Rect(int(self.x), top, self.width, int(self.gap_top - top))

    @property
    def bottom_rect(self) -> pygame.Rect:
        """Collision rect for the lower column."""
        top = int(self.gap_bottom)
        return pygame.Rect(int(self.x), top, self.width, config.SEABED_Y - top)

    def collides_with(self, rect: pygame.Rect) -> bool:
        """True if ``rect`` overlaps either column."""
        return bool(rect.colliderect(self.top_rect) or rect.colliderect(self.bottom_rect))

    @property
    def right(self) -> float:
        """Right edge x-position."""
        return self.x + self.width

    @property
    def center_x(self) -> float:
        """Horizontal centre of the column."""
        return self.x + self.width / 2

    def update(self, speed: float, dt: float = 1.0) -> None:
        """Scroll left by ``speed`` px per reference-frame."""
        self.x -= speed * dt

    def is_offscreen(self) -> bool:
        """True once the column has fully scrolled past the left edge."""
        return self.right < 0


class ObstacleField:
    """Manages the set of live obstacles: spawning, scrolling, and scoring."""

    def __init__(
        self, rng: random.Random | None = None, mode: "modes.Mode | None" = None
    ) -> None:
        """Create an empty field.

        Pass a seeded ``rng`` for reproducible runs and a ``mode`` to apply
        difficulty multipliers (defaults to Normal so existing callers/tests
        behave exactly as before).
        """
        self._rng: random.Random = rng if rng is not None else random.Random()
        self.mode: modes.Mode = mode if mode is not None else modes.default()
        self.obstacles: list[Obstacle] = []
        self._seed_counter: int = 0
        self.reset()

    def reset(self) -> None:
        """Clear all obstacles and queue the first one off the right edge."""
        self.obstacles.clear()
        self._seed_counter = 0
        first_x = config.SCREEN_WIDTH + config.OBSTACLE_FIRST_OFFSET
        self.obstacles.append(self._make_obstacle(first_x, score=0))

    # ------------------------------------------------------------------ #
    # Difficulty
    # ------------------------------------------------------------------ #
    @staticmethod
    def gap_for_score(score: int, mode: "modes.Mode | None" = None) -> float:
        """Return the gap size for a given score (shrinks as score rises).

        ``mode`` (default Normal) scales the gap and sets the floor, so the
        single-arg static form used by existing tests still yields Normal.
        """
        m = mode if mode is not None else modes.default()
        base = config.OBSTACLE_GAP_START - score * config.OBSTACLE_GAP_SHRINK_PER_POINT
        gap = base * m.gap_scale
        return clamp(gap, m.gap_min, config.OBSTACLE_GAP_START * m.gap_scale)

    @staticmethod
    def speed_for_score(score: int, mode: "modes.Mode | None" = None) -> float:
        """Return the scroll speed for a given score (ramps up, then caps)."""
        m = mode if mode is not None else modes.default()
        speed = config.OBSTACLE_SPEED_START + score * config.OBSTACLE_SPEED_RAMP_PER_POINT
        speed *= m.speed_scale
        return clamp(
            speed,
            config.OBSTACLE_SPEED_START * m.speed_scale,
            config.OBSTACLE_SPEED_MAX * m.speed_scale,
        )

    # ------------------------------------------------------------------ #
    # Spawning
    # ------------------------------------------------------------------ #
    def _random_gap_center(self, gap_size: float) -> float:
        """Pick a gap centre that keeps the gap clear of surface and seabed."""
        margin = config.OBSTACLE_EDGE_MARGIN
        lo = config.WATER_SURFACE_Y + margin + gap_size / 2
        hi = config.SEABED_Y - margin - gap_size / 2
        if lo >= hi:  # Degenerate (very tight) — centre it.
            return (config.WATER_SURFACE_Y + config.SEABED_Y) / 2
        return self._rng.uniform(lo, hi)

    def _make_obstacle(self, x: float, score: int) -> Obstacle:
        """Construct one obstacle appropriate to the current ``score``/mode."""
        gap_size = self.gap_for_score(score, self.mode)
        gap_center = self._random_gap_center(gap_size)
        self._seed_counter += 1
        return Obstacle(x, gap_center, gap_size, seed=self._seed_counter)

    @property
    def _spacing(self) -> float:
        """Horizontal spacing between columns for the active mode."""
        return config.OBSTACLE_SPACING * self.mode.spacing_scale

    # ------------------------------------------------------------------ #
    # Update / scoring
    # ------------------------------------------------------------------ #
    def update(self, score: int, whale_x: float, dt: float = 1.0) -> int:
        """Scroll obstacles, spawn/recycle, and return points scored this call.

        A point is scored when a column's centre passes the whale's x-position.
        """
        speed = self.speed_for_score(score, self.mode)
        gained = 0

        for obstacle in self.obstacles:
            obstacle.update(speed, dt)
            if not obstacle.passed and obstacle.center_x < whale_x:
                obstacle.passed = True
                gained += 1

        # Remove fully off-screen columns.
        self.obstacles = [o for o in self.obstacles if not o.is_offscreen()]

        # Spawn a new column once the last one is far enough onto the screen.
        if self.obstacles:
            last = self.obstacles[-1]
            if last.x <= config.SCREEN_WIDTH - self._spacing:
                new_x = last.x + self._spacing
                self.obstacles.append(self._make_obstacle(new_x, score + gained))
        else:
            self.obstacles.append(
                self._make_obstacle(config.SCREEN_WIDTH + config.OBSTACLE_FIRST_OFFSET, score)
            )

        return gained

    def collides(self, rect: pygame.Rect) -> bool:
        """True if ``rect`` hits any live column."""
        return any(o.collides_with(rect) for o in self.obstacles)

    # ------------------------------------------------------------------ #
    # Rendering
    # ------------------------------------------------------------------ #
    def draw(self, target: pygame.Surface, offset: tuple[float, float] = (0.0, 0.0)) -> None:
        """Draw every live column, building art lazily and caching per column."""
        from assets import draw as art  # rendering-only dependency

        for obstacle in self.obstacles:
            if obstacle._top_surface is None:
                color = config.CORAL_COLORS[obstacle.seed % len(config.CORAL_COLORS)]
                top_h = max(1, int(obstacle.gap_top - config.WATER_SURFACE_Y))
                bot_h = max(1, int(config.SEABED_Y - obstacle.gap_bottom))
                obstacle._top_surface = art.build_coral_column(
                    top_h, obstacle.width, color, flip=True, seed=obstacle.seed
                )
                obstacle._bottom_surface = art.build_coral_column(
                    bot_h, obstacle.width, color, flip=False, seed=obstacle.seed + 999
                )
            tx = obstacle.x + offset[0]
            target.blit(obstacle._top_surface, (tx, config.WATER_SURFACE_Y + offset[1]))
            target.blit(obstacle._bottom_surface, (tx, obstacle.gap_bottom + offset[1]))
