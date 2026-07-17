"""Tests for particle system lifecycle: emission, update, and culling."""

from __future__ import annotations

import random

import config
from particles import ParticleSystem


def test_spout_emits_bubbles() -> None:
    ps = ParticleSystem(random.Random(1))
    ps.emit_spout((100, 100))
    assert len(ps.bubbles) == config.SPOUT_BUBBLE_COUNT


def test_splash_emits_droplets() -> None:
    ps = ParticleSystem(random.Random(1))
    ps.emit_splash(100, 100)
    assert len(ps.splashes) == config.SPLASH_PARTICLE_COUNT


def test_score_pop_emits_one() -> None:
    ps = ParticleSystem(random.Random(1))
    ps.emit_score_pop(50, 50)
    assert len(ps.score_pops) == 1


def test_splashes_expire() -> None:
    ps = ParticleSystem(random.Random(1))
    ps.emit_splash(100, 100)
    for _ in range(config.SPLASH_LIFETIME + 2):
        ps.update(dt=1.0, spawn_ambient=False)
    assert len(ps.splashes) == 0


def test_score_pops_expire() -> None:
    ps = ParticleSystem(random.Random(1))
    ps.emit_score_pop(50, 50)
    for _ in range(config.SCORE_POP_LIFETIME + 2):
        ps.update(dt=1.0, spawn_ambient=False)
    assert len(ps.score_pops) == 0


def test_bubbles_rise() -> None:
    ps = ParticleSystem(random.Random(1))
    ps.emit_spout((100, 400))
    y_before = ps.bubbles[0].y
    ps.update(dt=1.0, spawn_ambient=False)
    assert ps.bubbles[0].y < y_before


def test_clear_removes_everything() -> None:
    ps = ParticleSystem(random.Random(1))
    ps.emit_spout((100, 100))
    ps.emit_splash(100, 100)
    ps.emit_score_pop(50, 50)
    ps.clear()
    assert ps.count == 0


def test_ambient_bubbles_can_spawn() -> None:
    # With chance forced high via many ticks, at least some bubbles appear.
    ps = ParticleSystem(random.Random(1))
    for _ in range(200):
        ps.update(dt=1.0, spawn_ambient=True)
    assert ps.count >= 1
