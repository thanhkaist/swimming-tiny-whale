"""Whale characters: distinct skins and subtly different physics feel.

A ``WhaleSpec`` bundles a colour palette with three physics multipliers. The
default "classic" whale uses neutral 1.0 scales and the base ``WHALE_*``
palette, so a default whale is numerically and visually identical to the
original. Pure data (no pygame) — safe to import anywhere and easy to test.
"""

from __future__ import annotations

from dataclasses import dataclass

import config

Color = tuple[int, int, int]


@dataclass(frozen=True)
class WhaleSpec:
    """One playable whale: palette + feel + unlock info."""

    id: str
    name: str
    tagline: str
    unlock_cost: int
    unlocked_by_default: bool
    gravity_scale: float
    impulse_scale: float
    hitbox_scale: float
    body: Color
    body_light: Color
    outline: Color
    belly: Color
    glow: Color


CHARACTERS: tuple[WhaleSpec, ...] = (
    WhaleSpec(
        id="classic", name="Classic", tagline="the original — balanced",
        unlock_cost=0, unlocked_by_default=True,
        gravity_scale=1.0, impulse_scale=1.0, hitbox_scale=1.0,
        body=config.WHALE_BODY, body_light=config.WHALE_BODY_LIGHT,
        outline=config.WHALE_OUTLINE, belly=config.WHALE_BELLY,
        glow=config.WHALE_GLOW,
    ),
    WhaleSpec(
        id="coral", name="Coral", tagline="floaty & gentle",
        unlock_cost=config.CHAR_CORAL_COST, unlocked_by_default=False,
        gravity_scale=0.82, impulse_scale=0.9, hitbox_scale=1.0,
        body=config.CHAR_CORAL_BODY, body_light=config.CHAR_CORAL_LIGHT,
        outline=config.CHAR_CORAL_OUTLINE, belly=config.CHAR_CORAL_BELLY,
        glow=config.CHAR_CORAL_GLOW,
    ),
    WhaleSpec(
        id="orca", name="Orca", tagline="heavy — strong swimmer",
        unlock_cost=config.CHAR_ORCA_COST, unlocked_by_default=False,
        gravity_scale=1.22, impulse_scale=1.14, hitbox_scale=1.0,
        body=config.CHAR_ORCA_BODY, body_light=config.CHAR_ORCA_LIGHT,
        outline=config.CHAR_ORCA_OUTLINE, belly=config.CHAR_ORCA_BELLY,
        glow=config.CHAR_ORCA_GLOW,
    ),
    WhaleSpec(
        id="pip", name="Pip", tagline="tiny — small hitbox",
        unlock_cost=config.CHAR_PIP_COST, unlocked_by_default=False,
        gravity_scale=1.0, impulse_scale=1.0, hitbox_scale=0.72,
        body=config.CHAR_PIP_BODY, body_light=config.CHAR_PIP_LIGHT,
        outline=config.CHAR_PIP_OUTLINE, belly=config.CHAR_PIP_BELLY,
        glow=config.CHAR_PIP_GLOW,
    ),
)

_BY_ID: dict[str, WhaleSpec] = {c.id: c for c in CHARACTERS}
DEFAULT: str = config.DEFAULT_CHARACTER


def by_id(char_id: str | None) -> WhaleSpec:
    """Return the character with ``char_id`` (falls back to the default)."""
    return _BY_ID.get(char_id or DEFAULT, _BY_ID[DEFAULT])


def default() -> WhaleSpec:
    """Return the default character spec."""
    return _BY_ID[DEFAULT]
