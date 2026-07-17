"""Non-column hazards: drifting jellyfish, sea mines, and current zones.

Jellyfish and mines are lethal on contact (a shield absorbs the hit, handled by
the game's single collision sink). Current zones don't kill — they push the
whale vertically while it is inside. All logic is display-independent and
deterministic from an injected RNG, so it unit-tests headless and daily runs
stay reproducible. Hazards scroll at the same speed as the coral columns, passed
in each frame by the game.
"""

from __future__ import annotations

import math
import random

import pygame

import config
import modes


class _Floating:
    """Shared behaviour for a circular hazard that scrolls and bobs."""

    def __init__(self, x: float, y: float, radius: int) -> None:
        self.x = float(x)
        self.y = float(y)
        self.radius = radius
        self.dead = False
        self._phase = 0.0

    def _scroll(self, speed: float, dt: float) -> None:
        self.x -= speed * dt
        self._phase += config.JELLYFISH_BOB_SPEED * dt

    @property
    def rect(self) -> pygame.Rect:
        r = self.radius
        rect = pygame.Rect(0, 0, int(r * 1.6), int(r * 1.6))
        rect.center = (int(self.x), int(self.draw_y))
        return rect

    @property
    def draw_y(self) -> float:
        return self.y

    def is_offscreen(self) -> bool:
        return self.x + self.radius < 0


class Jellyfish(_Floating):
    """A jellyfish that drifts left and bobs vertically. Lethal on contact."""

    lethal = True

    def __init__(self, x: float, y: float, rng: random.Random | None = None) -> None:
        super().__init__(x, y, config.JELLYFISH_RADIUS)
        self._base_y = float(y)
        self._phase = rng.uniform(0.0, math.tau) if rng else 0.0

    def update(self, speed: float, dt: float = 1.0) -> None:
        self._scroll(speed, dt)
        # Drift a touch slower than the current and bob for a floaty feel.
        self.x += speed * 0.15 * dt
        self.y = self._base_y + math.sin(self._phase) * config.JELLYFISH_BOB_AMP

    @property
    def draw_y(self) -> float:
        return self.y


class Mine(_Floating):
    """A spiky sea mine. Lethal on contact (shield-absorbable)."""

    lethal = True

    def __init__(self, x: float, y: float, rng: random.Random | None = None) -> None:
        super().__init__(x, y, config.MINE_RADIUS)
        self._base_y = float(y)
        self._phase = rng.uniform(0.0, math.tau) if rng else 0.0

    def update(self, speed: float, dt: float = 1.0) -> None:
        self._scroll(speed, dt)
        self.y = self._base_y + math.sin(self._phase) * 6.0


class CurrentZone:
    """A rectangular current that pushes the whale vertically (never lethal)."""

    lethal = False

    def __init__(self, x: float, top: float, push: float) -> None:
        self.x = float(x)
        self.top = float(top)
        self.width = config.CURRENT_WIDTH
        self.height = config.CURRENT_HEIGHT
        self.push = push  # signed: negative = up, positive = down
        self._phase = 0.0

    def update(self, speed: float, dt: float = 1.0) -> None:
        self.x -= speed * dt
        self._phase += 0.08 * dt

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.top), self.width, self.height)

    def contains(self, whale: "object") -> bool:
        return self.rect.colliderect(whale.rect)

    def is_offscreen(self) -> bool:
        return self.x + self.width < 0


class HazardField:
    """Spawns and updates hazards; reports lethal contacts to the game."""

    def __init__(
        self, rng: random.Random | None = None, mode: "modes.Mode | None" = None
    ) -> None:
        self._rng: random.Random = rng if rng is not None else random.Random()
        self.mode: modes.Mode = mode if mode is not None else modes.default()
        self.hazards: list = []      # jellyfish + mines
        self.currents: list = []     # current zones
        self._spawn_cd: float = config.HAZARD_SPAWN_INTERVAL
        self.reset()

    def reset(self) -> None:
        self.hazards.clear()
        self.currents.clear()
        self._spawn_cd = config.HAZARD_SPAWN_INTERVAL

    def update(
        self,
        speed: float,
        whale: "object",
        dt: float = 1.0,
        effects: "object | None" = None,
        score: int = 0,
    ) -> str | None:
        """Advance hazards; return ``"hit"`` if a lethal one touched the whale.

        Current zones apply their push to the whale directly and never kill.
        """
        hit: str | None = None
        for h in self.hazards:
            h.update(speed, dt)
            if not h.dead and h.rect.colliderect(whale.rect):
                h.dead = True
                hit = "hit"
        for cz in self.currents:
            cz.update(speed, dt)
            if cz.contains(whale):
                whale.vy += cz.push * dt

        self.hazards = [h for h in self.hazards if not h.dead and not h.is_offscreen()]
        self.currents = [c for c in self.currents if not c.is_offscreen()]

        self._spawn_cd -= dt
        if self._spawn_cd <= 0:
            jitter = 1.0 + self._rng.uniform(-config.HAZARD_SPAWN_JITTER, config.HAZARD_SPAWN_JITTER)
            self._spawn_cd = config.HAZARD_SPAWN_INTERVAL * jitter
            if score >= config.HAZARD_MIN_SCORE:
                self._spawn()
        return hit

    def _spawn(self) -> None:
        """Spawn one random hazard entering from the right edge."""
        margin = config.OBSTACLE_EDGE_MARGIN
        lo = config.WATER_SURFACE_Y + margin
        hi = config.SEABED_Y - margin
        choice = self._rng.random()
        x = config.SCREEN_WIDTH + 30
        if choice < 0.4:
            y = self._rng.uniform(lo, hi)
            self.hazards.append(Jellyfish(x, y, self._rng))
        elif choice < 0.72:
            y = self._rng.uniform(lo, hi)
            self.hazards.append(Mine(x, y, self._rng))
        else:
            top = self._rng.uniform(lo, hi - config.CURRENT_HEIGHT)
            top = max(config.WATER_SURFACE_Y, top)
            push = self._rng.choice((-1.0, 1.0)) * config.CURRENT_PUSH
            self.currents.append(CurrentZone(x, top, push))

    # ------------------------------------------------------------------ #
    # Rendering
    # ------------------------------------------------------------------ #
    def draw(self, target: pygame.Surface, offset: tuple[float, float] = (0.0, 0.0)) -> None:
        """Draw current zones (behind) then jellyfish/mines."""
        from assets import draw as art

        for cz in self.currents:
            band = pygame.Surface((cz.width, cz.height), pygame.SRCALPHA)
            band.fill((*config.CURRENT_COLOR, 40))
            # Directional chevrons hinting at the push.
            up = cz.push < 0
            for i in range(4):
                yy = (i * 44 + int(cz._phase * 14)) % cz.height
                tip = yy - 8 if up else yy + 8
                cxm = cz.width // 2
                pygame.draw.lines(band, (*config.CURRENT_COLOR, 150), False,
                                  [(cxm - 12, yy), (cxm, tip), (cxm + 12, yy)], 2)
            target.blit(band, (cz.x + offset[0], cz.top + offset[1]))

        for h in self.hazards:
            if isinstance(h, Jellyfish):
                sprite = art.build_jellyfish(h.radius)
            else:
                sprite = art.build_mine(h.radius)
            target.blit(sprite, sprite.get_rect(center=(h.x + offset[0], h.draw_y + offset[1])))
