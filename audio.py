"""Procedural sound effects with graceful headless degradation.

No external audio files: swim/score/hit blips are synthesised as short PCM
buffers at startup. If the mixer cannot initialise (e.g. a headless server with
no audio device) every method becomes a silent no-op and the game runs on. The
whole subsystem is toggleable at runtime.
"""

from __future__ import annotations

import array
import math

import pygame

# Mixer format we request; must match the sample buffers we synthesise.
_SAMPLE_RATE = 44100
_AMPLITUDE = 0.28  # keep it gentle


class Audio:
    """Owns the synthesised SFX and a mute toggle. Safe to use even if muted."""

    def __init__(self) -> None:
        self.available: bool = False
        self.enabled: bool = True
        self._sounds: dict[str, pygame.mixer.Sound] = {}
        self._rate: int = _SAMPLE_RATE
        self._channels: int = 1
        self._init_mixer()
        if self.available:
            self._build_sounds()

    def _init_mixer(self) -> None:
        """Bring up the mixer; synthesise to whatever format it actually uses.

        ``pygame.init()`` may already have opened the mixer (often in stereo),
        in which case our requested format would be ignored and mono buffers
        would play back garbled. We read the *actual* init format and match our
        synthesis to it, so playback is correct regardless of how it was opened.
        """
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.pre_init(_SAMPLE_RATE, -16, 1, 512)
                pygame.mixer.init()
            actual = pygame.mixer.get_init()
            if not actual:
                self.available = False
                return
            self._rate, _size, self._channels = actual
            self.available = True
        except pygame.error:
            self.available = False

    # ------------------------------------------------------------------ #
    # Synthesis
    # ------------------------------------------------------------------ #
    def _tone(
        self,
        freq_start: float,
        freq_end: float,
        duration: float,
        wave: str = "sine",
    ) -> "pygame.mixer.Sound":
        """Synthesise a 16-bit tone gliding start→end freq, matching mixer format.

        Emits ``self._channels`` interleaved samples per step at ``self._rate``
        so the buffer is correct whether the mixer opened mono or stereo.
        """
        n = int(self._rate * duration)
        buf = array.array("h", bytes(0))
        buf_append = buf.append
        phase = 0.0
        for i in range(n):
            t = i / n
            freq = freq_start + (freq_end - freq_start) * t
            phase += freq / self._rate
            if wave == "square":
                sample = 1.0 if (phase % 1.0) < 0.5 else -1.0
            else:  # sine
                sample = math.sin(phase * math.tau)
            # Short attack + exponential release envelope for a soft blip.
            env = min(1.0, t * 12.0) * (1.0 - t) ** 1.4
            value = int(_AMPLITUDE * env * sample * 32767)
            for _ in range(self._channels):  # interleave for stereo if needed
                buf_append(value)
        return pygame.mixer.Sound(buffer=buf.tobytes())

    def _build_sounds(self) -> None:
        """Create the three effects (swim, score, hit)."""
        try:
            self._sounds["swim"] = self._tone(320, 560, 0.14, "sine")
            self._sounds["score"] = self._tone(660, 990, 0.16, "sine")
            self._sounds["hit"] = self._tone(300, 90, 0.32, "square")
        except (pygame.error, ValueError):
            # If synthesis fails for any reason, drop to silent.
            self.available = False
            self._sounds.clear()

    # ------------------------------------------------------------------ #
    # Playback
    # ------------------------------------------------------------------ #
    def play(self, name: str) -> None:
        """Play a named effect if audio is available and enabled."""
        if not self.available or not self.enabled:
            return
        sound = self._sounds.get(name)
        if sound is not None:
            try:
                sound.play()
            except pygame.error:
                pass

    def toggle(self) -> bool:
        """Flip mute state; return the new ``enabled`` value."""
        self.enabled = not self.enabled
        return self.enabled
