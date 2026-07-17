"""In-field collectibles: coins the whale grabs while swimming.

The field scrolls at the same speed as the coral columns (passed in each frame
from the game so parallax and fairness hold), spawns coins in short clusters
aimed at the upcoming gap, supports a magnet pull, and reports what was
collected. All logic is display-independent so it unit-tests headless; only
``draw`` touches surfaces.

The design leaves room for power-up pickups (Phase 5): every item carries a
``kind`` and ``update`` already routes non-coin kinds out separately.
"""

from __future__ import annotations

import math
import random

import pygame

import config
import modes
import powerups
from util import clamp, lerp


class Collectible:
    """Base class for anything floating in the field the whale can grab."""

    kind: str = "collectible"

    def __init__(self, x: float, y: float, radius: int) -> None:
        self.x = float(x)
        self.y = float(y)
        self.radius = radius
        self.collected = False
        self._bob_phase = 0.0

    def update(self, speed: float, dt: float = 1.0) -> None:
        """Scroll left with the field and bob gently."""
        self.x -= speed * dt
        self._bob_phase += config.COIN_BOB_SPEED * dt

    @property
    def rect(self) -> pygame.Rect:
        """Square hitbox centred on the collectible."""
        r = self.radius
        rect = pygame.Rect(0, 0, r * 2, r * 2)
        rect.center = (int(self.x), int(self.draw_y))
        return rect

    @property
    def draw_y(self) -> float:
        """Y including the idle bob (used for both drawing and collision)."""
        return self.y + math.sin(self._bob_phase) * config.COIN_BOB_AMPLITUDE

    def is_offscreen(self) -> bool:
        """True once fully scrolled past the left edge."""
        return self.x + self.radius < 0


class Coin(Collectible):
    """A gold coin worth ``config.COIN_VALUE``."""

    kind = "coin"

    def __init__(self, x: float, y: float, rng: random.Random | None = None) -> None:
        super().__init__(x, y, config.COIN_RADIUS)
        self.value = config.COIN_VALUE
        # Desync the bob so a cluster shimmers rather than moving in lockstep.
        self._bob_phase = rng.uniform(0.0, math.tau) if rng else 0.0


class PowerUp(Collectible):
    """A floating power-up; ``kind`` is one of ``powerups.IDS``."""

    def __init__(self, x: float, y: float, kind: str) -> None:
        super().__init__(x, y, config.POWERUP_RADIUS)
        self.kind = kind


class CollectibleField:
    """Spawns, scrolls, and collects coins and power-ups."""

    def __init__(
        self, rng: random.Random | None = None, mode: "modes.Mode | None" = None
    ) -> None:
        self._rng: random.Random = rng if rng is not None else random.Random()
        self.mode: modes.Mode = mode if mode is not None else modes.default()
        self.items: list[Collectible] = []
        self._spawn_cooldown: float = config.COIN_SPAWN_INTERVAL
        self.reset()

    def reset(self) -> None:
        """Clear all items and reset the spawn timer."""
        self.items.clear()
        self._spawn_cooldown = config.COIN_SPAWN_INTERVAL

    # ------------------------------------------------------------------ #
    # Update / collection
    # ------------------------------------------------------------------ #
    def update(
        self,
        speed: float,
        whale: "object",
        obstacle_field: "object | None" = None,
        dt: float = 1.0,
        effects: "object | None" = None,
    ) -> tuple[int, list[str]]:
        """Advance the field one tick.

        Returns ``(coins_collected, powerup_kinds)`` — the coin value gained
        this tick and any non-coin pickups (empty until power-ups exist).
        """
        magnet = bool(effects is not None and getattr(effects, "magnet", False))
        coins = 0
        powerups: list[str] = []

        for item in self.items:
            if item.collected:
                continue
            item.update(speed, dt)
            if magnet:
                pull = clamp(config.COIN_MAGNET_LERP * dt, 0.0, 1.0)
                item.x = lerp(item.x, whale.x, pull)
                item.y = lerp(item.y, whale.y, pull)
            if item.rect.colliderect(whale.rect):
                item.collected = True
                if item.kind == "coin":
                    coins += getattr(item, "value", config.COIN_VALUE)
                else:
                    powerups.append(item.kind)

        self.items = [i for i in self.items if not i.collected and not i.is_offscreen()]

        self._spawn_cooldown -= dt
        if self._spawn_cooldown <= 0:
            jitter = 1.0 + self._rng.uniform(-config.COIN_SPAWN_JITTER, config.COIN_SPAWN_JITTER)
            self._spawn_cooldown = config.COIN_SPAWN_INTERVAL * jitter
            self._spawn_cluster(obstacle_field)

        return coins, powerups

    def _spawn_y(self, obstacle_field: "object | None") -> float:
        """Choose a spawn height, aimed at the newest gap when available."""
        margin = config.OBSTACLE_EDGE_MARGIN
        lo = config.WATER_SURFACE_Y + margin
        hi = config.SEABED_Y - margin
        obstacles = getattr(obstacle_field, "obstacles", None)
        if obstacles:
            gap_center = obstacles[-1].gap_center
            jitter = self._rng.uniform(-config.COIN_GAP_JITTER, config.COIN_GAP_JITTER)
            return clamp(gap_center + jitter, lo, hi)
        return self._rng.uniform(lo, hi)

    def _spawn_cluster(self, obstacle_field: "object | None") -> None:
        """Spawn either a power-up or a short run of coins, entering right."""
        y = self._spawn_y(obstacle_field)
        if self._rng.random() < config.POWERUP_SPAWN_CHANCE:
            kind = self._rng.choice(powerups.IDS)
            x = config.SCREEN_WIDTH + config.POWERUP_RADIUS * 2
            self.items.append(PowerUp(x, y, kind))
            return
        count = self._rng.randint(1, config.COIN_CLUSTER_MAX)
        x0 = config.SCREEN_WIDTH + config.COIN_RADIUS * 2
        for k in range(count):
            self.items.append(Coin(x0 + k * config.COIN_CLUSTER_SPACING, y, self._rng))

    # ------------------------------------------------------------------ #
    # Rendering
    # ------------------------------------------------------------------ #
    def draw(self, target: pygame.Surface, offset: tuple[float, float] = (0.0, 0.0)) -> None:
        """Draw every live coin with a soft glow."""
        from assets import draw as art  # rendering-only dependency

        for item in self.items:
            if item.collected:
                continue
            cx = item.x + offset[0]
            cy = item.draw_y + offset[1]
            if item.kind == "coin":
                glow = art.radial_glow(item.radius + 6, config.COIN_SHINE, 60)
                sprite = art.build_coin(item.radius)
            else:
                kind = powerups.by_id(item.kind)
                glow = art.radial_glow(item.radius + 8, kind.color, 90)
                sprite = art.build_powerup(item.kind, kind.color, item.radius)
            target.blit(glow, glow.get_rect(center=(cx, cy)))
            target.blit(sprite, sprite.get_rect(center=(cx, cy)))
