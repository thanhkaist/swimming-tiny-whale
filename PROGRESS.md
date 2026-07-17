# Progress — Swimming Tiny Whale

Built autonomously in one session. Status: **complete, playable, polished, and
tested.** All 51 tests pass; the game runs cleanly headless and at ~3 ms/frame
(comfortably under the 16.6 ms 60-FPS budget).

## What got built (in order)

1. **Playable MVP** — physics, coral obstacles, scoring, collision, game over,
   and the title/playing/gameover state machine.
2. **Visual polish** — underwater gradient, god-ray light shafts, parallax
   layers (kelp, distant fish, plankton), the animated whale (idle bob,
   tail-flap, velocity tilt, bubble spout), rounded hand-crafted coral columns.
3. **Juice pass** — rising bubbles, impact splash + screen shake + white flash,
   score "+1" pops, an animated HUD score pop, a depth vignette, and smooth
   cross-fades between screens.
4. **Tests** — 51 pytest tests covering physics, collision, scoring, obstacle
   difficulty, particles, persistence, and the full state machine — all
   headless (`SDL_VIDEODRIVER=dummy`).
5. **Polish + refactor** — no magic numbers (everything in `config.py`), type
   hints and docstrings throughout, pyflakes-clean, README + this file.

## Decisions I made along the way (no one to ask)

- **God-rays rebuilt.** The first version used additive blending, which adds a
  beam's full-brightness RGB regardless of its alpha and blasted solid white
  wedges across the screen. Switched to a cached, depth-faded, feathered-edge
  beam sprite blended normally — soft, believable shafts. (This was the single
  biggest visual fix; see the two commits.)
- **Frame-rate-independent physics** via a normalised `dt` (1.0 == one frame at
  60 FPS), clamped to 2.5 to avoid a spiral-of-death on a laggy frame. Kept the
  classic Flappy feel while being correct.
- **Forgiving hitbox** — the whale's collision rect is a bit smaller than its
  art, which feels fairer and is standard for this genre.
- **Difficulty curve** — gap shrinks `2.2px`/point (floored at 158px) and speed
  ramps `0.06`/point (capped at 5.2px/frame). Gentle, not punishing early.
- **Pre-start hover** — after the title→play fade, the whale hovers with a "Tap
  to swim!" prompt until the first flap, so a run never starts before you're
  ready.
- **Audio is synthesised, not sampled** — swim/score/hit are generated as PCM
  buffers at startup (no files to ship) and the whole subsystem no-ops if the
  mixer can't init, so it's fine on a headless box.
- **Procedural art with a deterministic per-column RNG** (a tiny LCG) so coral
  silhouettes are varied but reproducible and cacheable — no per-frame rebuilds.
- **Added `util.py` and `storage.py`** beyond the CLAUDE.md module list to keep
  math helpers and persistence cleanly separated and independently testable.

## What I'd polish next

- **Real audio playtest.** SFX are synthesised and wired, but this was a
  headless build — I couldn't listen. The envelopes/frequencies are reasonable
  but would benefit from a human ear (and maybe a soft ambient underwater loop).
- **Whale sprite depth.** It's cute, but a subtle outline/rim-light and a soft
  drop shadow beneath it would make it pop more against the god-rays.
- **Coral variety.** Currently four colour variants + procedural bumps. Could
  add a couple of distinct silhouettes (branching coral, anemone tops, bubble
  vents) and occasional foreground coral that scrolls slightly faster.
- **Medals / milestones.** A bronze/silver/gold medal on the game-over panel at
  score thresholds, plus a little celebratory particle burst on a new best.
- **Death animation.** The whale currently sinks; a brief dizzy/spin or "×_×"
  face would add character.
- **Settings surface.** Expose an on-screen mute toggle and maybe a difficulty
  selector rather than only the `M` key.
- **Parallax depth on god-rays** relative to screen shake, and caustic ripples
  on the seabed, for extra atmosphere.
- **Gamepad support** and a configurable key-binding layer.

## How to verify quickly

```bash
source venv/bin/activate
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pytest -q          # tests
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python main.py --frames 120  # smoke
python main.py                                                           # play
```
