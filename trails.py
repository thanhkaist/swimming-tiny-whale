"""Cosmetic trails: a stream of particles left behind the swimming whale.

Pure data (no pygame); the game reads a trail's colour(s) and emits particles.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import config

Color = tuple[int, int, int]


@dataclass(frozen=True)
class Trail:
    """One cosmetic trail option."""

    id: str
    name: str
    cost: int
    colors: tuple[Color, ...] = field(default_factory=tuple)

    @property
    def is_none(self) -> bool:
        """True for the empty 'no trail' option."""
        return self.id == config.DEFAULT_TRAIL


TRAILS: tuple[Trail, ...] = (
    Trail(id=config.DEFAULT_TRAIL, name="None", cost=0),
    Trail(id="bubbles", name="Bubbles", cost=config.TRAIL_BUBBLES_COST,
          colors=(config.TRAIL_BUBBLES_COLOR,)),
    Trail(id="sparkle", name="Sparkle", cost=config.TRAIL_SPARKLE_COST,
          colors=(config.TRAIL_SPARKLE_COLOR,)),
    Trail(id="rainbow", name="Rainbow", cost=config.TRAIL_RAINBOW_COST,
          colors=config.TRAIL_RAINBOW_COLORS),
)

_BY_ID: dict[str, Trail] = {t.id: t for t in TRAILS}


def by_id(trail_id: str | None) -> Trail:
    """Return the trail with ``trail_id`` (falls back to 'none')."""
    return _BY_ID.get(trail_id or config.DEFAULT_TRAIL, _BY_ID[config.DEFAULT_TRAIL])
