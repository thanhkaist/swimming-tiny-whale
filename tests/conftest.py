"""Shared test setup: force pygame into fully headless mode.

Importing pygame is fine without a display, but any surface/font/mixer use
needs the dummy drivers. Setting these before pygame initialises anywhere keeps
the entire logic suite runnable on a headless server / CI.
"""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402  (import after env is set, by design)


def pytest_configure(config) -> None:  # noqa: ANN001 - pytest hook signature
    """Initialise pygame once for the whole session (headless-safe)."""
    pygame.display.init()
    pygame.display.set_mode((64, 64))  # a video mode is needed for convert()/rotate
    pygame.font.init()
