# Project: Swimming Tiny Whale (Flappy Bird-style, Python + pygame)

## Code standards
- Python 3, PEP 8, type hints on all functions, docstrings on classes/public methods.
- Separate concerns: game logic, rendering, input, and config in distinct modules.
- No magic numbers — all tunables (gravity, impulse, gap size, speeds, colors, FPS)
  live in config.py as named constants.
- Keep the main loop thin; delegate to update()/draw() methods.

## Structure
- main.py     # entry point + game loop + state machine
- whale.py    # player entity: physics, animation, tilt
- obstacles.py# coral/seaweed columns, spawning, scrolling
- particles.py# bubbles, splash, score pop
- scene.py    # background: gradient, god-rays, parallax layers
- config.py   # all constants
- assets/     # any generated/procedural art helpers

## Constraints (headless server)
- Must run without a display for testing: honor SDL_VIDEODRIVER=dummy.
- Audio must degrade gracefully — game runs fine if sound init fails.
- Core mechanics (physics, collision, scoring) must be unit-testable without a window.

## Workflow
- Commit to git after each working milestone with a clear message.
- Prefer procedural/vector-drawn art over external image files so it runs anywhere.
