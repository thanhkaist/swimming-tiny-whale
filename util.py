"""Small, dependency-free math helpers shared across modules.

Kept separate from game logic so they can be unit-tested trivially and reused
by rendering, physics, and particle code without circular imports.
"""

from __future__ import annotations


def clamp(value: float, low: float, high: float) -> float:
    """Return ``value`` constrained to the inclusive range ``[low, high]``."""
    if value < low:
        return low
    if value > high:
        return high
    return value


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation from ``a`` to ``b`` by fraction ``t``."""
    return a + (b - a) * t


def ease_out_cubic(t: float) -> float:
    """Cubic ease-out on a normalised ``t`` in ``[0, 1]``."""
    t = clamp(t, 0.0, 1.0)
    f = t - 1.0
    return f * f * f + 1.0


def ease_in_out_sine(t: float) -> float:
    """Sine-based ease-in-out on a normalised ``t`` in ``[0, 1]``."""
    import math

    t = clamp(t, 0.0, 1.0)
    return -(math.cos(math.pi * t) - 1.0) / 2.0


def lerp_color(
    c1: tuple[int, int, int],
    c2: tuple[int, int, int],
    t: float,
) -> tuple[int, int, int]:
    """Interpolate between two RGB colors, returning integer channels."""
    t = clamp(t, 0.0, 1.0)
    return (
        int(round(lerp(c1[0], c2[0], t))),
        int(round(lerp(c1[1], c2[1], t))),
        int(round(lerp(c1[2], c2[2], t))),
    )
