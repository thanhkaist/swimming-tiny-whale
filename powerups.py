"""Power-ups and the timed-effect manager.

Pure logic (no pygame) so it unit-tests headless. Every timer counts in frames
and is decremented by the *real* frame delta — never by the slowed world time —
so slow-mo lasts a fixed wall-clock duration regardless of the slowdown it
itself causes.
"""

from __future__ import annotations

from dataclasses import dataclass

import config

# Power-up ids.
SHIELD = "shield"
SLOWMO = "slowmo"
MAGNET = "magnet"
SHRINK = "shrink"


@dataclass(frozen=True)
class PowerUpKind:
    """Static description of a power-up type."""

    id: str
    name: str
    duration: float
    color: tuple[int, int, int]


POWERUPS: tuple[PowerUpKind, ...] = (
    PowerUpKind(SHIELD, "Shield", config.SHIELD_DURATION, config.POWERUP_SHIELD_COLOR),
    PowerUpKind(SLOWMO, "Slow-mo", config.SLOWMO_DURATION, config.POWERUP_SLOWMO_COLOR),
    PowerUpKind(MAGNET, "Magnet", config.MAGNET_DURATION, config.POWERUP_MAGNET_COLOR),
    PowerUpKind(SHRINK, "Shrink", config.SHRINK_DURATION, config.POWERUP_SHRINK_COLOR),
)

_BY_ID: dict[str, PowerUpKind] = {p.id: p for p in POWERUPS}
IDS: tuple[str, ...] = tuple(p.id for p in POWERUPS)


def by_id(kind_id: str) -> PowerUpKind:
    """Return the power-up kind for ``kind_id`` (raises KeyError if unknown)."""
    return _BY_ID[kind_id]


class EffectManager:
    """Tracks active timed effects and exposes their combined influence."""

    def __init__(self) -> None:
        self.active: dict[str, float] = {}   # kind -> frames remaining

    def activate(self, kind: str) -> None:
        """(Re)start ``kind`` at its full duration."""
        if kind in _BY_ID:
            self.active[kind] = _BY_ID[kind].duration

    def update(self, dt: float = 1.0) -> None:
        """Count every active effect down by REAL ``dt`` frames; cull expired."""
        for kind in list(self.active):
            self.active[kind] -= dt
            if self.active[kind] <= 0:
                del self.active[kind]

    def clear(self) -> None:
        """Remove all active effects (used on reset)."""
        self.active.clear()

    # -- combined influence --------------------------------------------- #
    @property
    def time_scale(self) -> float:
        """World time multiplier (slowest active slow-mo, else 1.0)."""
        return config.SLOWMO_TIME_SCALE if SLOWMO in self.active else 1.0

    @property
    def magnet(self) -> bool:
        """True while the coin magnet is active."""
        return MAGNET in self.active

    @property
    def shield(self) -> bool:
        """True while a shield is up."""
        return SHIELD in self.active

    @property
    def hitbox_scale(self) -> float:
        """Extra hitbox multiplier from Shrink (1.0 when not shrunk)."""
        return config.SHRINK_HITBOX_SCALE if SHRINK in self.active else 1.0

    def consume_shield(self) -> bool:
        """Spend the shield on a hit. Return True if one was available."""
        if SHIELD in self.active:
            del self.active[SHIELD]
            return True
        return False

    def is_active(self, kind: str) -> bool:
        """True if ``kind`` is currently active."""
        return kind in self.active

    def hud_items(self) -> list[tuple[str, tuple[int, int, int], float]]:
        """Return ``(kind, color, fraction_remaining)`` for each active effect."""
        items = []
        for kind in IDS:  # stable display order
            if kind in self.active:
                frac = max(0.0, min(1.0, self.active[kind] / _BY_ID[kind].duration))
                items.append((kind, _BY_ID[kind].color, frac))
        return items
