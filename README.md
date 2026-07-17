# 🐳 Swimming Tiny Whale

A cute, juicy **Flappy Bird-style** game built in Python + pygame. Guide a chubby
little whale through drifting coral columns in a soft, sun-dappled sea.

All art is drawn procedurally (no image files), so it runs anywhere — and the
core mechanics run headlessly for testing.

![gameplay](docs/gameplay.png)

## Features

- 🌊 **Living underwater scene** — a deep-teal→aqua gradient, soft god-ray light
  shafts that sway and breathe, drifting plankton, distant parallax fish, and
  swaying kelp fronds.
- 🐳 **A friendly whale** — chubby and round, with an idle bob, a tail-flap
  animation, velocity-based tilt, and a little bubble spout each time it swims.
- 🪸 **Hand-crafted coral obstacles** — rounded, knobbly, colourful columns with
  sprouting seaweed (not plain pipes). Difficulty ramps: the gap tightens and
  the current speeds up as your score climbs.
- ✨ **Juice** — rising bubbles, a splash burst and screen shake on impact, a
  white flash, a satisfying score "+1" pop, and smooth cross-fades between
  screens.
- 🏆 **Persistent high score** saved to a local file.
- 🔊 **Optional sound** — swim / score / hit blips are synthesised at runtime
  (no audio files) and degrade gracefully to silent if there's no audio device.
- 🎯 **60 FPS**, frame-rate-independent physics.

## Controls

| Action            | Keys / Mouse                     |
|-------------------|----------------------------------|
| Swim up           | **Space**, **↑**, **W**, or click |
| Start / restart   | Same swim input                  |
| Mute / unmute     | **M**                            |
| Quit              | **Esc**                          |

The whale sinks constantly under gentle gravity — tap to give it an upward swim
impulse and thread the coral gaps. Hitting a column, the water surface, or the
seabed ends the run.

## Running

Requires **Python 3** and **pygame**. A virtualenv is included; from the project
root:

```bash
# Using the bundled venv
source venv/bin/activate
python main.py
```

Or set up fresh:

```bash
python3 -m venv venv
source venv/bin/activate
pip install pygame
python main.py
```

### Headless / smoke run

The game honours `SDL_VIDEODRIVER=dummy` and can self-exit after N frames, which
is handy on a server with no display:

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python main.py --frames 120
```

## Tests

Core logic (physics, collision, scoring, obstacle difficulty, particles,
persistence, and the state machine) is unit-tested **without needing a display**:

```bash
source venv/bin/activate
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pytest -q
```

## Project layout

```
main.py       # entry point, game loop, title/playing/gameover state machine
whale.py      # player entity: physics, tilt, tail-flap animation
obstacles.py  # coral/seaweed columns: spawning, scrolling, scoring, collision
particles.py  # bubbles, swim spout, impact splash, score pop
scene.py      # background: gradient, god-rays, parallax layers, vignette
audio.py      # synthesised, gracefully-degrading sound effects
storage.py    # local high-score persistence
util.py       # small math helpers (clamp, lerp, easing)
config.py     # every tunable constant (physics, colours, sizes, feel)
assets/draw.py# procedural art (whale sprite, coral columns, god-rays, vignette)
tests/        # pytest suite (headless)
```

All gameplay tunables — gravity, swim impulse, gap sizes, speeds, colours, FPS —
live in `config.py`, so the feel is easy to tweak in one place.
