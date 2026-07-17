"""Game modes: difficulty presets and the daily-challenge seed.

A ``Mode`` is a small immutable bundle of multipliers the obstacle field applies
on top of the base difficulty curve, plus a couple of behavioural flags. Modes
are pure data (no pygame), so this module is trivially testable and importable
anywhere without a display.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

import config


@dataclass(frozen=True)
class Mode:
    """One selectable difficulty / challenge preset."""

    id: str
    name: str
    tagline: str
    gap_scale: float        # multiplies the (score-derived) gap size
    gap_min: int            # hard floor on the gap for this mode
    speed_scale: float      # multiplies scroll speed
    spacing_scale: float    # multiplies horizontal spacing between columns
    no_death: bool          # True → collisions never end the run (Zen)
    is_daily: bool          # True → run is seeded deterministically per day


MODES: tuple[Mode, ...] = (
    Mode(
        id="zen", name="Zen", tagline="drift & relax — no game over",
        gap_scale=config.MODE_ZEN_GAP_SCALE, gap_min=config.MODE_ZEN_GAP_MIN,
        speed_scale=config.MODE_ZEN_SPEED_SCALE, spacing_scale=1.0,
        no_death=True, is_daily=False,
    ),
    Mode(
        id="normal", name="Normal", tagline="the classic swim",
        gap_scale=1.0, gap_min=config.OBSTACLE_GAP_MIN,
        speed_scale=1.0, spacing_scale=1.0,
        no_death=False, is_daily=False,
    ),
    Mode(
        id="hard", name="Hard", tagline="tighter gaps, faster current",
        gap_scale=config.MODE_HARD_GAP_SCALE, gap_min=config.MODE_HARD_GAP_MIN,
        speed_scale=config.MODE_HARD_SPEED_SCALE,
        spacing_scale=config.MODE_HARD_SPACING_SCALE,
        no_death=False, is_daily=False,
    ),
    Mode(
        id="daily", name="Daily", tagline="same run for everyone today",
        gap_scale=1.0, gap_min=config.OBSTACLE_GAP_MIN,
        speed_scale=1.0, spacing_scale=1.0,
        no_death=False, is_daily=True,
    ),
)

_BY_ID: dict[str, Mode] = {m.id: m for m in MODES}


def by_id(mode_id: str | None) -> Mode:
    """Return the mode with ``mode_id`` (falls back to the default mode)."""
    return _BY_ID.get(mode_id or config.DEFAULT_MODE, _BY_ID[config.DEFAULT_MODE])


def default() -> Mode:
    """Return the default mode."""
    return _BY_ID[config.DEFAULT_MODE]


def daily_seed(date: datetime.date) -> int:
    """Return a deterministic integer seed for ``date`` (YYYYMMDD)."""
    return int(date.strftime("%Y%m%d"))


def today_seed() -> int:
    """Return the daily seed for the current local date."""
    return daily_seed(datetime.date.today())
