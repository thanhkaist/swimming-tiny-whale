"""The player entity: a chubby, friendly whale.

Physics (gravity, swim impulse, velocity clamping, tilt) are kept independent
of rendering so they can be unit-tested without a display. Sprite surfaces are
built lazily on the first ``draw`` call, so constructing and simulating a whale
never requires a video mode to be set.
"""

from __future__ import annotations

import math

import pygame

import config
from util import clamp, lerp


class Whale:
    """A whale that sinks under gravity and swims upward on demand."""

    def __init__(
        self,
        x: float | None = None,
        y: float | None = None,
        spec: "object | None" = None,
    ) -> None:
        """Create a whale at ``(x, y)`` using ``spec`` (defaults to Classic).

        ``spec`` is a ``characters.WhaleSpec``; the default is numerically and
        visually identical to the original whale (neutral 1.0 scales, base
        palette), so existing callers/tests are unaffected.
        """
        import characters  # local import avoids a module-load cycle

        self.spec = spec if spec is not None else characters.default()
        self.x: float = float(config.WHALE_START_X if x is None else x)
        self.y: float = float(config.WHALE_START_Y if y is None else y)
        self.vy: float = 0.0
        self.width: int = config.WHALE_WIDTH
        self.height: int = config.WHALE_HEIGHT
        # Base hitbox scale from the spec; power-ups (Phase 5) may lower it live.
        self.hitbox_scale: float = self.spec.hitbox_scale

        # Visual-only state.
        self.tilt: float = 0.0            # Current drawn tilt in degrees.
        self.flap_phase: float = 0.0      # Tail animation accumulator (radians).
        self.flap_energy: float = 0.0     # Extra flap speed right after a swim.
        self.bob_phase: float = 0.0       # Idle bob accumulator.
        self.alive: bool = True

        # Lazily built, tilt/flap dependent sprite cache.
        self._sprite_cache: dict[int, pygame.Surface] = {}
        self._glow: pygame.Surface | None = None

    # ------------------------------------------------------------------ #
    # Physics
    # ------------------------------------------------------------------ #
    def swim(self) -> None:
        """Apply an upward impulse (the flap), scaled by the character."""
        self.vy = config.SWIM_IMPULSE * self.spec.impulse_scale
        self.flap_energy = config.WHALE_TAIL_FLAP_SWIM_BOOST

    def update(self, dt: float = 1.0, apply_gravity: bool = True) -> None:
        """Advance physics by ``dt`` frames (1.0 == one reference frame).

        When ``apply_gravity`` is False the whale free-floats (used on the
        title screen for the idle bob).
        """
        if apply_gravity:
            self.vy += config.GRAVITY * self.spec.gravity_scale * dt
            self.vy = clamp(self.vy, config.MAX_RISE_SPEED, config.MAX_FALL_SPEED)
            self.y += self.vy * dt

        self._update_animation(dt)

    def _update_animation(self, dt: float) -> None:
        """Advance tilt, tail-flap, and bob accumulators."""
        # Tilt eases toward a target derived from vertical velocity.
        target_tilt = clamp(
            -self.vy * config.WHALE_TILT_VELOCITY_SCALE,
            config.WHALE_MAX_TILT_DOWN,
            config.WHALE_MAX_TILT_UP,
        )
        self.tilt = lerp(self.tilt, target_tilt, config.WHALE_TILT_EASING)

        # Tail flaps faster briefly after a swim, then settles to a gentle idle.
        flap_speed = config.WHALE_TAIL_FLAP_SPEED + self.flap_energy
        self.flap_phase += flap_speed * dt
        self.flap_energy = max(0.0, self.flap_energy - 0.06 * dt)

        self.bob_phase += config.WHALE_BOB_SPEED * dt

    def idle_bob(self, base_y: float, dt: float = 1.0) -> None:
        """Float gently around ``base_y`` (title screen only)."""
        self.bob_phase += config.WHALE_BOB_SPEED * dt
        self.y = base_y + math.sin(self.bob_phase) * config.WHALE_BOB_AMPLITUDE
        self.vy = math.cos(self.bob_phase) * 1.2  # feed the tilt a little life
        self._update_animation(dt)

    # ------------------------------------------------------------------ #
    # Collision
    # ------------------------------------------------------------------ #
    @property
    def rect(self) -> pygame.Rect:
        """Forgiving collision rectangle (a little smaller than the art).

        The character's ``hitbox_scale`` (1.0 for most, smaller for tiny whales
        or while shrunk by a power-up) shrinks it further. At scale 1.0 this is
        identical to the original hitbox.
        """
        w = (self.width - config.WHALE_HITBOX_SHRINK_X) * self.hitbox_scale
        h = (self.height - config.WHALE_HITBOX_SHRINK_Y) * self.hitbox_scale
        rect = pygame.Rect(0, 0, int(round(w)), int(round(h)))
        rect.center = (int(self.x), int(self.y))
        return rect

    def hits_bounds(self) -> bool:
        """True if the whale has touched the surface or the seabed."""
        r = self.rect
        return r.top <= config.WATER_SURFACE_Y or r.bottom >= config.SEABED_Y

    @property
    def spout_origin(self) -> tuple[float, float]:
        """World position where swim-spout bubbles should emit (the blowhole)."""
        return (self.x + self.width * 0.18, self.y - self.height * 0.34)

    # ------------------------------------------------------------------ #
    # Rendering
    # ------------------------------------------------------------------ #
    def _get_sprite(self) -> pygame.Surface:
        """Return the base (upright) sprite for the current flap phase.

        Cached in coarse phase buckets so we build only a handful of surfaces
        total rather than one per frame.
        """
        from assets import draw  # local import: rendering-only dependency

        bucket = int((self.flap_phase % math.tau) / math.tau * 12) % 12
        sprite = self._sprite_cache.get(bucket)
        if sprite is None:
            phase = bucket / 12 * math.tau
            sprite = draw.build_whale_surface(phase, self.spec)
            self._sprite_cache[bucket] = sprite
        return sprite

    def draw(self, target: pygame.Surface, offset: tuple[float, float] = (0.0, 0.0)) -> None:
        """Draw the whale onto ``target`` — soft glow halo, then tilted sprite."""
        cx, cy = self.x + offset[0], self.y + offset[1]

        if self._glow is None:
            from assets import draw  # rendering-only dependency

            self._glow = draw.radial_glow(int(self.width * 0.95), self.spec.glow, 70)
        glow_rect = self._glow.get_rect(center=(cx, cy))
        target.blit(self._glow, glow_rect)

        sprite = self._get_sprite()
        rotated = pygame.transform.rotate(sprite, self.tilt)
        rect = rotated.get_rect(center=(cx, cy))
        target.blit(rotated, rect)

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def reset(self) -> None:
        """Reset physics/visual state for a new run."""
        self.x = float(config.WHALE_START_X)
        self.y = float(config.WHALE_START_Y)
        self.vy = 0.0
        self.tilt = 0.0
        self.flap_energy = 0.0
        self.hitbox_scale = self.spec.hitbox_scale
        self.alive = True
