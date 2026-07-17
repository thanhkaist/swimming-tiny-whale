"""Particle systems: rising bubbles, the swim spout, impact splash, score pops.

Each particle updates purely with arithmetic, so the systems simulate fine
headless; only ``draw`` touches surfaces. A single ``ParticleSystem`` owns all
live particles and exposes small emitter methods the game calls on events.
"""

from __future__ import annotations

import math
import random

import pygame

import config


class Bubble:
    """A rising, gently wobbling bubble."""

    def __init__(self, x: float, y: float, radius: float, speed: float, rng: random.Random) -> None:
        self.x = x
        self.y = y
        self.radius = radius
        self.speed = speed
        self.age = 0
        self.lifetime = config.BUBBLE_LIFETIME
        self._wobble_phase = rng.uniform(0.0, math.tau)
        self._wobble_speed = rng.uniform(0.04, 0.12)

    def update(self, dt: float = 1.0) -> bool:
        """Advance; return True while still alive."""
        self.y -= self.speed * dt
        self._wobble_phase += self._wobble_speed * dt
        self.x += math.sin(self._wobble_phase) * config.BUBBLE_WOBBLE_AMPLITUDE * dt
        self.age += dt
        return self.age < self.lifetime and self.y + self.radius > config.WATER_SURFACE_Y

    def draw(self, target: pygame.Surface, offset: tuple[float, float]) -> None:
        fade = 1.0 - (self.age / self.lifetime)
        alpha = int(clamp_alpha(150 * fade))
        if alpha <= 0:
            return
        r = int(self.radius)
        surf = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(surf, (*config.BUBBLE_COLOR, alpha), (r + 1, r + 1), r, width=1)
        pygame.draw.circle(surf, (*config.BUBBLE_COLOR, alpha // 2), (r + 1, r + 1), max(1, r - 1))
        # tiny highlight
        pygame.draw.circle(surf, (255, 255, 255, alpha), (r, r - r // 2 + 1), max(1, r // 3))
        target.blit(surf, (self.x - r + offset[0], self.y - r + offset[1]))


class Splash:
    """A short-lived droplet flung out on impact."""

    def __init__(self, x: float, y: float, vx: float, vy: float, radius: float) -> None:
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.radius = radius
        self.age = 0
        self.lifetime = config.SPLASH_LIFETIME

    def update(self, dt: float = 1.0) -> bool:
        self.vy += config.SPLASH_GRAVITY * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.age += dt
        return self.age < self.lifetime

    def draw(self, target: pygame.Surface, offset: tuple[float, float]) -> None:
        fade = 1.0 - (self.age / self.lifetime)
        alpha = int(clamp_alpha(220 * fade))
        if alpha <= 0:
            return
        r = max(1, int(self.radius * fade))
        surf = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(surf, (*config.SPLASH_COLOR, alpha), (r + 1, r + 1), r)
        target.blit(surf, (self.x - r + offset[0], self.y - r + offset[1]))


class ScorePop:
    """A rising, fading '+1' text pop at the point a column is cleared."""

    def __init__(self, x: float, y: float, text: str = "+1") -> None:
        self.x = x
        self.y = y
        self.text = text
        self.age = 0
        self.lifetime = config.SCORE_POP_LIFETIME

    def update(self, dt: float = 1.0) -> bool:
        self.y -= config.SCORE_POP_RISE * dt
        self.age += dt
        return self.age < self.lifetime

    def draw(self, target: pygame.Surface, font: pygame.font.Font, offset: tuple[float, float]) -> None:
        t = self.age / self.lifetime
        # Pop in with a slight overshoot, then fade.
        scale = 1.0 + 0.3 * math.sin(min(1.0, t * 2) * math.pi)
        alpha = int(clamp_alpha(255 * (1.0 - t)))
        if alpha <= 0:
            return
        base = font.render(self.text, True, config.TEXT_ACCENT)
        w = max(1, int(base.get_width() * scale))
        h = max(1, int(base.get_height() * scale))
        img = pygame.transform.smoothscale(base, (w, h))
        img.set_alpha(alpha)
        rect = img.get_rect(center=(self.x + offset[0], self.y + offset[1]))
        target.blit(img, rect)


class TrailBit:
    """A small coloured dot left behind the whale (cosmetic trail)."""

    def __init__(self, x: float, y: float, color: tuple[int, int, int]) -> None:
        self.x = x
        self.y = y
        self.color = color
        self.age = 0
        self.lifetime = config.TRAIL_LIFETIME

    def update(self, dt: float = 1.0) -> bool:
        # Drift gently back and up, like it is being left in the wake.
        self.x -= 0.6 * dt
        self.y -= 0.25 * dt
        self.age += dt
        return self.age < self.lifetime

    def draw(self, target: pygame.Surface, offset: tuple[float, float]) -> None:
        fade = 1.0 - (self.age / self.lifetime)
        alpha = int(clamp_alpha(200 * fade))
        if alpha <= 0:
            return
        r = max(1, int(5 * fade))
        surf = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(surf, (*self.color, alpha), (r + 1, r + 1), r)
        target.blit(surf, (self.x - r + offset[0], self.y - r + offset[1]))


def clamp_alpha(value: float) -> float:
    """Clamp an alpha value into the valid 0..255 range."""
    return max(0.0, min(255.0, value))


class ParticleSystem:
    """Owns and drives every live particle in the scene."""

    def __init__(self, rng: random.Random | None = None) -> None:
        self._rng: random.Random = rng if rng is not None else random.Random()
        self.bubbles: list[Bubble] = []
        self.splashes: list[Splash] = []
        self.score_pops: list[ScorePop] = []
        self.trail_bits: list[TrailBit] = []

    # ------------------------------------------------------------------ #
    # Emitters
    # ------------------------------------------------------------------ #
    def emit_ambient_bubble(self) -> None:
        """Occasionally spawn a bubble drifting up from the deep."""
        if self._rng.random() > config.BUBBLE_SPAWN_CHANCE:
            return
        x = self._rng.uniform(0, config.SCREEN_WIDTH)
        y = config.SEABED_Y + self._rng.uniform(-10, 6)
        radius = self._rng.uniform(config.BUBBLE_MIN_RADIUS, config.BUBBLE_MAX_RADIUS)
        speed = self._rng.uniform(config.BUBBLE_RISE_SPEED_MIN, config.BUBBLE_RISE_SPEED_MAX)
        self.bubbles.append(Bubble(x, y, radius, speed, self._rng))

    def emit_spout(self, origin: tuple[float, float]) -> None:
        """Emit a little burst of bubbles from the whale's blowhole on a swim."""
        ox, oy = origin
        for _ in range(config.SPOUT_BUBBLE_COUNT):
            x = ox + self._rng.uniform(-6, 6)
            y = oy + self._rng.uniform(-4, 4)
            radius = self._rng.uniform(config.BUBBLE_MIN_RADIUS, config.BUBBLE_MAX_RADIUS - 1)
            speed = self._rng.uniform(config.SPOUT_SPEED_MIN, config.SPOUT_SPEED_MAX)
            self.bubbles.append(Bubble(x, y, radius, speed, self._rng))

    def emit_splash(self, x: float, y: float) -> None:
        """Emit an impact burst of droplets at ``(x, y)``."""
        for _ in range(config.SPLASH_PARTICLE_COUNT):
            angle = self._rng.uniform(0, math.tau)
            speed = self._rng.uniform(config.SPLASH_SPEED_MIN, config.SPLASH_SPEED_MAX)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed - 1.5  # bias slightly upward
            radius = self._rng.uniform(2, 5)
            self.splashes.append(Splash(x, y, vx, vy, radius))

    def emit_score_pop(self, x: float, y: float, text: str = "+1") -> None:
        """Emit a rising ``text`` (defaults to '+1') at ``(x, y)``."""
        self.score_pops.append(ScorePop(x, y, text))

    def emit_trail(self, x: float, y: float, color: tuple[int, int, int]) -> None:
        """Emit one cosmetic trail bit at ``(x, y)``."""
        self.trail_bits.append(TrailBit(x, y, color))

    # ------------------------------------------------------------------ #
    # Update / draw
    # ------------------------------------------------------------------ #
    def update(self, dt: float = 1.0, spawn_ambient: bool = True) -> None:
        """Advance every particle; cull dead ones."""
        if spawn_ambient:
            self.emit_ambient_bubble()
        self.bubbles = [b for b in self.bubbles if b.update(dt)]
        self.splashes = [s for s in self.splashes if s.update(dt)]
        self.score_pops = [p for p in self.score_pops if p.update(dt)]
        self.trail_bits = [t for t in self.trail_bits if t.update(dt)]

    def draw(
        self,
        target: pygame.Surface,
        pop_font: pygame.font.Font | None = None,
        offset: tuple[float, float] = (0.0, 0.0),
    ) -> None:
        """Draw all particles. ``pop_font`` is needed for score pops."""
        for trail in self.trail_bits:
            trail.draw(target, offset)
        for bubble in self.bubbles:
            bubble.draw(target, offset)
        for splash in self.splashes:
            splash.draw(target, offset)
        if pop_font is not None:
            for pop in self.score_pops:
                pop.draw(target, pop_font, offset)

    def clear(self) -> None:
        """Remove all particles (used on reset)."""
        self.bubbles.clear()
        self.splashes.clear()
        self.score_pops.clear()
        self.trail_bits.clear()

    @property
    def count(self) -> int:
        """Total live particle count (handy for tests/debugging)."""
        return (len(self.bubbles) + len(self.splashes)
                + len(self.score_pops) + len(self.trail_bits))
