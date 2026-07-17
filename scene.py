"""The underwater backdrop: gradient, god-rays, parallax layers, surface, seabed.

The scene owns slow ambient motion (drifting plankton, distant fish, swaying
kelp and light shafts) that runs in every game state to keep the world alive.
The static gradient is rendered once and cached. All motion is deterministic
given a seeded RNG.
"""

from __future__ import annotations

import math
import random

import pygame

import config
from util import clamp


class _Plankton:
    """A tiny drifting speck in the mid-water."""

    def __init__(self, rng: random.Random) -> None:
        self.x = rng.uniform(0, config.SCREEN_WIDTH)
        self.y = rng.uniform(config.WATER_SURFACE_Y, config.SEABED_Y)
        self.size = rng.uniform(1.0, 2.6)
        self.speed = rng.uniform(0.05, config.PLANKTON_DRIFT_SPEED)
        self.phase = rng.uniform(0, math.tau)
        self.bob = rng.uniform(0.2, 0.7)
        self.alpha = rng.randint(40, 120)

    def update(self, dt: float) -> None:
        self.x -= self.speed * dt
        self.phase += 0.03 * dt
        self.y += math.sin(self.phase) * self.bob * dt
        if self.x < -4:
            self.x = config.SCREEN_WIDTH + 4


class _FarFish:
    """A distant, slow silhouette fish for depth (background parallax)."""

    def __init__(self, rng: random.Random) -> None:
        self.x = rng.uniform(0, config.SCREEN_WIDTH)
        self.y = rng.uniform(config.WATER_SURFACE_Y + 40, config.SEABED_Y - 60)
        self.speed = rng.uniform(config.FAR_FISH_SPEED_MIN, config.FAR_FISH_SPEED_MAX)
        self.size = rng.uniform(6, 12)
        self.phase = rng.uniform(0, math.tau)

    def update(self, dt: float) -> None:
        self.x -= self.speed * dt
        self.phase += 0.02 * dt
        self.y += math.sin(self.phase) * 0.25 * dt
        if self.x < -20:
            self.x = config.SCREEN_WIDTH + 20
            self.y = _rng_between(config.WATER_SURFACE_Y + 40, config.SEABED_Y - 60)

    def draw(self, target: pygame.Surface, offset: tuple[float, float]) -> None:
        col = config.FAR_FISH_COLOR
        x, y = self.x + offset[0] * 0.3, self.y + offset[1] * 0.3
        body = pygame.Rect(0, 0, int(self.size * 1.8), int(self.size))
        body.center = (int(x), int(y))
        surf = pygame.Surface((body.width + 10, body.height + 6), pygame.SRCALPHA)
        cx, cy = surf.get_width() // 2, surf.get_height() // 2
        pygame.draw.ellipse(surf, (*col, 70), (2, 3, body.width, body.height))
        pygame.draw.polygon(
            surf, (*col, 70),
            [(body.width, cy), (body.width + 8, cy - 4), (body.width + 8, cy + 4)],
        )
        target.blit(surf, (body.x - 2, body.y - 3))


class _Kelp:
    """A tall swaying kelp frond rooted at the seabed (slow parallax)."""

    def __init__(self, rng: random.Random) -> None:
        self.x = rng.uniform(0, config.SCREEN_WIDTH)
        self.height = rng.uniform(120, 260)
        self.phase = rng.uniform(0, math.tau)
        self.sway = rng.uniform(6, 16)
        self.width = rng.randint(6, 11)
        self.light = rng.random() > 0.5

    def update(self, dt: float) -> None:
        self.x -= config.PARALLAX_KELP_SPEED * dt
        self.phase += 0.02 * dt
        if self.x < -30:
            self.x = config.SCREEN_WIDTH + 30

    def draw(self, target: pygame.Surface, offset: tuple[float, float]) -> None:
        color = config.KELP_COLOR_LIGHT if self.light else config.KELP_COLOR
        base_x = self.x + offset[0] * 0.5
        base_y = config.SEABED_Y
        segments = 10
        prev = (base_x, base_y)
        for i in range(1, segments + 1):
            t = i / segments
            sway = math.sin(self.phase + t * 3.0) * self.sway * t
            px = base_x + sway
            py = base_y - t * self.height
            pygame.draw.line(target, color, prev, (px, py), max(2, int(self.width * (1 - t) + 1)))
            prev = (px, py)


_module_rng = random.Random(1234)


def _rng_between(a: float, b: float) -> float:
    return _module_rng.uniform(a, b)


class Scene:
    """The animated underwater background."""

    def __init__(self, rng: random.Random | None = None) -> None:
        self._rng = rng if rng is not None else random.Random(20240718)
        self.time: float = 0.0

        from assets import draw as art
        self._gradient = art.vertical_gradient(
            config.SCREEN_WIDTH, config.SCREEN_HEIGHT,
            config.GRADIENT_TOP, config.GRADIENT_BOTTOM,
        )
        ray_len = config.SEABED_Y - config.WATER_SURFACE_Y
        self._godray_sprite = art.build_godray(
            ray_len, top_w=22, bottom_w=64,
            color=config.GODRAY_COLOR, max_alpha=config.GODRAY_MAX_ALPHA,
        )

        self.plankton = [_Plankton(self._rng) for _ in range(config.PLANKTON_COUNT)]
        self.fish = [_FarFish(self._rng) for _ in range(config.FAR_FISH_COUNT)]
        self.kelp = [_Kelp(self._rng) for _ in range(config.PARALLAX_KELP_COUNT)]
        # Each ray gets a base x, a sway phase, and a slight tilt for variety.
        self._godrays = [
            {
                "base_x": (i + 0.5) / config.GODRAY_COUNT * config.SCREEN_WIDTH,
                "phase": self._rng.uniform(0, math.tau),
                "tilt": self._rng.uniform(-8, 8),
                "speed": self._rng.uniform(0.8, 1.3),
            }
            for i in range(config.GODRAY_COUNT)
        ]

    # ------------------------------------------------------------------ #
    # Update
    # ------------------------------------------------------------------ #
    def update(self, dt: float = 1.0) -> None:
        """Advance all ambient background motion."""
        self.time += dt
        for p in self.plankton:
            p.update(dt)
        for f in self.fish:
            f.update(dt)
        for k in self.kelp:
            k.update(dt)

    # ------------------------------------------------------------------ #
    # Draw
    # ------------------------------------------------------------------ #
    def draw(self, target: pygame.Surface, offset: tuple[float, float] = (0.0, 0.0)) -> None:
        """Draw the full backdrop (behind gameplay entities)."""
        target.blit(self._gradient, (0, 0))
        self._draw_godrays(target)
        for k in self.kelp:
            k.draw(target, offset)
        for f in self.fish:
            f.draw(target, offset)
        self._draw_plankton(target, offset)
        self._draw_surface(target, offset)
        self._draw_seabed(target, offset)

    def _draw_godrays(self, target: pygame.Surface) -> None:
        """Draw soft, slowly swaying light shafts descending from the surface."""
        for ray in self._godrays:
            phase = ray["phase"] + self.time * config.GODRAY_SPEED * ray["speed"]
            sway = math.sin(phase) * 26
            # Gentle breathing of the beam's brightness.
            brightness = 0.55 + 0.45 * (0.5 + 0.5 * math.sin(phase * 0.6))
            tilt = ray["tilt"] + math.sin(phase * 0.5) * 3
            sprite = pygame.transform.rotate(self._godray_sprite, tilt)
            # Modulate overall beam brightness (works on per-pixel-alpha surfaces).
            sprite = sprite.copy()
            mul = int(clamp(255 * brightness, 0, 255))
            sprite.fill((255, 255, 255, mul), special_flags=pygame.BLEND_RGBA_MULT)
            x = ray["base_x"] + sway - sprite.get_width() / 2
            # Normal alpha blend: the beam's low per-pixel alpha keeps it soft.
            target.blit(sprite, (x, config.WATER_SURFACE_Y))

    def _draw_plankton(self, target: pygame.Surface, offset: tuple[float, float]) -> None:
        for p in self.plankton:
            r = max(1, int(p.size))
            surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*config.PLANKTON_COLOR, p.alpha), (r, r), r)
            target.blit(surf, (p.x - r + offset[0] * 0.6, p.y - r + offset[1] * 0.6))

    def _draw_surface(self, target: pygame.Surface, offset: tuple[float, float]) -> None:
        """Draw the shimmering water surface band at the top."""
        surf_h = config.WATER_SURFACE_Y
        band = pygame.Surface((config.SCREEN_WIDTH, surf_h), pygame.SRCALPHA)
        band.fill((*config.SURFACE_COLOR, 60))
        # Moving highlight ripples.
        for i in range(6):
            phase = self.time * 0.03 + i
            x = (i / 6 * config.SCREEN_WIDTH + math.sin(phase) * 24) % config.SCREEN_WIDTH
            y = surf_h - 8 + math.sin(phase * 2) * 3
            pygame.draw.ellipse(
                band, (*config.SURFACE_HIGHLIGHT, 120),
                (x - 18, y, 36, 6),
            )
        target.blit(band, (0, offset[1] * 0.2))
        pygame.draw.line(
            target, config.SURFACE_HIGHLIGHT,
            (0, surf_h), (config.SCREEN_WIDTH, surf_h), 2,
        )

    def _draw_seabed(self, target: pygame.Surface, offset: tuple[float, float]) -> None:
        """Draw the sandy seabed band at the bottom with gentle dunes."""
        top = config.SEABED_Y
        h = config.SCREEN_HEIGHT - top
        band = pygame.Surface((config.SCREEN_WIDTH, h + 10), pygame.SRCALPHA)
        band.fill((*config.SEABED_COLOR, 255))
        # Dune highlights.
        for i in range(0, config.SCREEN_WIDTH, 44):
            wob = math.sin((i + self.time * 0.2) * 0.05) * 4
            pygame.draw.ellipse(
                band, (*config.SEABED_DARK, 120),
                (i - 10, 6 + wob, 60, 14),
            )
        target.blit(band, (0, top))
        pygame.draw.line(target, config.SEABED_DARK, (0, top), (config.SCREEN_WIDTH, top), 2)
