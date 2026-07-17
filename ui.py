"""Shared UI drawing helpers for the menu/overlay screens.

Pure drawing functions (no game state) so the main loop stays thin and the
title / leaderboard / mode / character / shop panels all share one look.
"""

from __future__ import annotations

import math

import pygame

import config
from util import clamp, ease_out_cubic, lerp


def slide_panel(
    screen: pygame.Surface,
    state_time: float,
    panel_w: int,
    panel_h: int,
    ramp: float = 26.0,
    alpha: int = 238,
) -> pygame.Rect:
    """Draw a centred rounded panel that eases down into place; return its rect."""
    t = ease_out_cubic(clamp(state_time / ramp, 0.0, 1.0))
    panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    pygame.draw.rect(panel, (*config.PANEL_COLOR, alpha), panel.get_rect(), border_radius=26)
    pygame.draw.rect(panel, (*config.PANEL_BORDER, 255), panel.get_rect(), width=3, border_radius=26)
    prect = panel.get_rect(center=(config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT // 2))
    prect.y = int(lerp(-panel_h, config.SCREEN_HEIGHT // 2 - panel_h // 2, t))
    screen.blit(panel, prect)
    return prect


def highlight_row(screen: pygame.Surface, rect: pygame.Rect, radius: int = 12) -> None:
    """Draw the soft selection highlight behind a menu row."""
    hi = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(hi, (*config.PANEL_BORDER, 52), hi.get_rect(), border_radius=radius)
    screen.blit(hi, rect)


def pulse_footer(
    screen: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    prect: pygame.Rect,
    state_time: float,
    dy: int = 24,
) -> None:
    """Draw a gently pulsing footer line near the bottom of ``prect``."""
    pulse = 0.5 + 0.5 * math.sin(state_time * 0.09)
    img = font.render(text, True, config.TEXT_COLOR)
    img.set_alpha(int(120 + 135 * pulse))
    screen.blit(img, img.get_rect(center=(prect.centerx, prect.bottom - dy)))
