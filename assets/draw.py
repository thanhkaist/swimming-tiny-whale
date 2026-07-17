"""Reusable procedural drawing routines.

These build ``pygame.Surface`` art at runtime: vertical gradients, soft blobs,
the whale sprite, and coral/seaweed columns. Everything is cached where it is
static so we do not rebuild surfaces every frame.

All functions are safe to import without a display; they only touch surfaces,
never the screen, and pygame surface creation works under the dummy driver.
"""

from __future__ import annotations

import math

import pygame

import config
from util import lerp_color


def vertical_gradient(
    width: int,
    height: int,
    top: tuple[int, int, int],
    bottom: tuple[int, int, int],
) -> pygame.Surface:
    """Return a surface filled with a smooth vertical gradient.

    Drawn once per resize (effectively once) so a per-row loop is fine.
    """
    surface = pygame.Surface((width, height)).convert()
    for y in range(height):
        t = y / max(1, height - 1)
        pygame.draw.line(surface, lerp_color(top, bottom, t), (0, y), (width, y))
    return surface


def build_godray(
    length: int,
    top_w: int,
    bottom_w: int,
    color: tuple[int, int, int],
    max_alpha: int,
) -> pygame.Surface:
    """Build one soft light shaft: bright near the surface, fading with depth.

    The beam widens as it descends and has feathered horizontal edges, so
    several of these blitted additively read as gentle god-rays rather than
    hard white wedges. Built once and cached by the scene.
    """
    width = max(top_w, bottom_w) + 8
    surf = pygame.Surface((width, length), pygame.SRCALPHA)
    cx = width / 2
    for y in range(length):
        t = y / max(1, length - 1)
        # Fade to nothing well before the seabed for an airy look.
        vfade = max(0.0, 1.0 - (t / 0.82) ** 1.3)
        row_alpha = max_alpha * vfade
        if row_alpha <= 0.5:
            continue
        w = top_w + (bottom_w - top_w) * t
        # Three feathered passes: wide+faint, mid, narrow+bright.
        for frac, amul in ((1.0, 0.35), (0.6, 0.6), (0.3, 1.0)):
            half = max(1.0, w * frac / 2)
            a = int(row_alpha * amul)
            if a <= 0:
                continue
            pygame.draw.line(surf, (*color, a), (cx - half, y), (cx + half, y))
    return surf


def radial_glow(
    radius: int,
    color: tuple[int, int, int],
    max_alpha: int,
) -> pygame.Surface:
    """Return a soft circular glow (alpha fades to 0 at the edge)."""
    size = radius * 2
    surface = pygame.Surface((size, size), pygame.SRCALPHA)
    for r in range(radius, 0, -1):
        t = r / radius
        alpha = int(max_alpha * (1.0 - t) ** 1.5)
        pygame.draw.circle(surface, (*color, alpha), (radius, radius), r)
    return surface


def soft_circle(
    radius: int,
    color: tuple[int, int, int],
    alpha: int = 255,
) -> pygame.Surface:
    """A single anti-aliased-ish filled circle on its own alpha surface."""
    size = radius * 2 + 2
    surface = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(surface, (*color, alpha), (radius + 1, radius + 1), radius)
    return surface


def _blob_points(
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    steps: int = 28,
) -> list[tuple[float, float]]:
    """Return points around an ellipse (used for smooth rounded bodies)."""
    pts = []
    for i in range(steps):
        ang = (i / steps) * math.tau
        pts.append((cx + math.cos(ang) * rx, cy + math.sin(ang) * ry))
    return pts


def build_whale_surface(flap_phase: float) -> pygame.Surface:
    """Build the whale sprite for a given tail-flap phase.

    Returns an upright (facing right) RGBA surface. Callers rotate it to apply
    tilt. ``flap_phase`` (radians) drives the tail's up/down swing so the whale
    looks like it is gently swimming.
    """
    w, h = config.WHALE_WIDTH, config.WHALE_HEIGHT
    pad = 16  # room for the tail swing and outline
    surf = pygame.Surface((w + pad * 2, h + pad * 2), pygame.SRCALPHA)
    ox, oy = pad, pad  # origin offset of the body box within the padded surface

    body_cx = ox + w * 0.46
    body_cy = oy + h * 0.5
    body_rx = w * 0.44
    body_ry = h * 0.5

    tail_swing = math.sin(flap_phase) * 8.0

    # --- Tail (behind the body) --------------------------------------------
    tail_base_x = ox + w * 0.04
    tail_top = (tail_base_x - 12, body_cy - 15 + tail_swing)
    tail_bot = (tail_base_x - 12, body_cy + 15 + tail_swing * 0.6)
    tail_mid = (tail_base_x + 8, body_cy)
    pygame.draw.polygon(
        surf,
        config.WHALE_BODY,
        [tail_top, tail_mid, tail_bot],
    )
    pygame.draw.polygon(
        surf,
        config.WHALE_BODY_LIGHT,
        [tail_top, tail_mid, ((tail_top[0] + tail_mid[0]) / 2, (tail_top[1] + tail_mid[1]) / 2)],
    )

    # --- Body (rounded blob) ------------------------------------------------
    body_pts = _blob_points(body_cx, body_cy, body_rx, body_ry)
    pygame.draw.polygon(surf, config.WHALE_BODY, body_pts)
    # Lighter top for a soft top-lit look.
    top_pts = _blob_points(body_cx, body_cy - body_ry * 0.28, body_rx * 0.92, body_ry * 0.55)
    pygame.draw.polygon(surf, config.WHALE_BODY_LIGHT, top_pts)

    # --- Belly (lighter underside) -----------------------------------------
    belly_pts = _blob_points(body_cx + 3, body_cy + body_ry * 0.42, body_rx * 0.72, body_ry * 0.42)
    pygame.draw.polygon(surf, config.WHALE_BELLY, belly_pts)

    # --- Side fin -----------------------------------------------------------
    fin_x = body_cx - 2
    fin_y = body_cy + body_ry * 0.36
    fin_swing = math.sin(flap_phase + 1.0) * 3.0
    pygame.draw.polygon(
        surf,
        config.WHALE_BODY_LIGHT,
        [
            (fin_x, fin_y),
            (fin_x - 14, fin_y + 10 + fin_swing),
            (fin_x + 4, fin_y + 12),
        ],
    )

    # --- Cheek blush --------------------------------------------------------
    cheek = soft_circle(5, config.WHALE_CHEEK, 150)
    surf.blit(cheek, (int(body_cx + body_rx * 0.34), int(body_cy + 2)))

    # --- Eye ----------------------------------------------------------------
    eye_x = int(body_cx + body_rx * 0.5)
    eye_y = int(body_cy - body_ry * 0.18)
    pygame.draw.circle(surf, config.WHALE_BELLY, (eye_x, eye_y), 6)
    pygame.draw.circle(surf, config.WHALE_EYE, (eye_x + 1, eye_y), 4)
    pygame.draw.circle(surf, (255, 255, 255), (eye_x + 2, eye_y - 2), 1)

    # --- Smile --------------------------------------------------------------
    smile_rect = pygame.Rect(0, 0, 16, 12)
    smile_rect.center = (eye_x - 1, eye_y + 10)
    pygame.draw.arc(surf, config.WHALE_EYE, smile_rect, math.pi * 1.15, math.pi * 1.95, 2)

    return surf


def build_coral_column(
    height: int,
    width: int,
    color: tuple[int, int, int],
    flip: bool,
    seed: int,
) -> pygame.Surface:
    """Build a rounded, hand-crafted-looking coral/seaweed column.

    ``flip`` True draws the column hanging from the top (roots up); False draws
    it growing from the bottom. ``seed`` makes each column's silhouette unique
    but deterministic (no per-frame randomness → cacheable).
    """
    surf = pygame.Surface((width, height), pygame.SRCALPHA)
    rng = _SeededRng(seed)

    # Main trunk: a rounded vertical body with a bulbous mouth at the gap end.
    trunk_w = int(width * 0.62)
    trunk_x = (width - trunk_w) // 2
    body_color = color
    shadow = config.CORAL_SHADOW

    # The "mouth" (gap-facing) end is at y=0 when flip, else at y=height.
    if flip:
        mouth_y = height
        _draw_coral_body(surf, trunk_x, 0, trunk_w, height, body_color, shadow, mouth_top=False)
    else:
        mouth_y = 0
        _draw_coral_body(surf, trunk_x, 0, trunk_w, height, body_color, shadow, mouth_top=True)

    # Knobbly coral bumps down the sides for a soft, organic silhouette.
    bump_count = max(3, height // 46)
    for i in range(bump_count):
        t = (i + 0.5) / bump_count
        by = int(t * height)
        br = rng.randint(8, 15)
        side = -1 if (i % 2 == 0) else 1
        bx = trunk_x + (0 if side < 0 else trunk_w) + side * br // 2
        tint = lerp_color(body_color, (255, 255, 255), 0.18)
        pygame.draw.circle(surf, tint, (bx, by), br)
        pygame.draw.circle(surf, body_color, (bx, by), br - 3)

    # A few seaweed fronds sprouting from the mouth end.
    frond_count = rng.randint(2, 4)
    for _ in range(frond_count):
        fx = trunk_x + rng.randint(4, trunk_w - 4)
        _draw_frond(surf, fx, mouth_y, height, flip, rng)

    return surf


def _draw_coral_body(
    surf: pygame.Surface,
    x: int,
    y: int,
    w: int,
    h: int,
    color: tuple[int, int, int],
    shadow: tuple[int, int, int],
    mouth_top: bool,
) -> None:
    """Draw the rounded trunk with a bulbous lip on the mouth side."""
    radius = w // 2
    rect = pygame.Rect(x, y, w, h)
    pygame.draw.rect(surf, color, rect, border_radius=radius)

    # Vertical light stripe for a bit of dimensional shading.
    light = lerp_color(color, (255, 255, 255), 0.22)
    stripe = pygame.Rect(x + w // 6, y + 4, max(3, w // 5), h - 8)
    pygame.draw.rect(surf, light, stripe, border_radius=stripe.width // 2)

    # Subtle inner shadow on the far side.
    dark = lerp_color(color, shadow, 0.35)
    sh = pygame.Rect(x + w - w // 4, y + 4, max(3, w // 6), h - 8)
    pygame.draw.rect(surf, dark, sh, border_radius=sh.width // 2)

    # Bulbous lip at the mouth end (the rounded cap facing the gap).
    lip_y = y if mouth_top else y + h
    lip = pygame.Rect(0, 0, w + 14, 26)
    lip.center = (x + w // 2, lip_y)
    pygame.draw.ellipse(surf, color, lip)
    lip_light = pygame.Rect(0, 0, w, 16)
    lip_light.center = (x + w // 2, lip_y - (4 if mouth_top else -4))
    pygame.draw.ellipse(surf, light, lip_light)


def _draw_frond(
    surf: pygame.Surface,
    x: int,
    mouth_y: int,
    height: int,
    flip: bool,
    rng: "_SeededRng",
) -> None:
    """Draw a wavy seaweed frond curling away from the mouth."""
    length = rng.randint(24, 54)
    direction = -1 if flip else 1  # frond points away from the gap
    segments = 8
    prev = (x, mouth_y)
    sway = rng.uniform(0.4, 1.1)
    color = config.SEAWEED_COLOR if rng.randint(0, 1) else config.SEAWEED_COLOR_DARK
    for s in range(1, segments + 1):
        t = s / segments
        py = mouth_y - direction * int(t * length) if flip else mouth_y + direction * int(t * length)
        # When flip, mouth is at bottom (height) growing up; guard bounds.
        py = mouth_y + direction * int(t * length)
        px = x + int(math.sin(t * math.pi * 1.5) * 8 * sway)
        pygame.draw.line(surf, color, prev, (px, py), max(2, 4 - s // 3))
        prev = (px, py)


class _SeededRng:
    """A tiny deterministic RNG (LCG) so art is reproducible per seed.

    We avoid the global ``random`` module here so building art never disturbs
    the game's own randomness stream and remains fully deterministic per seed.
    """

    def __init__(self, seed: int) -> None:
        self._state = (seed * 2654435761 + 12345) & 0xFFFFFFFF

    def _next(self) -> int:
        self._state = (1103515245 * self._state + 12345) & 0x7FFFFFFF
        return self._state

    def randint(self, a: int, b: int) -> int:
        """Inclusive integer in ``[a, b]``."""
        return a + self._next() % (b - a + 1)

    def uniform(self, a: float, b: float) -> float:
        """Float in ``[a, b)``."""
        return a + (self._next() / 0x7FFFFFFF) * (b - a)
