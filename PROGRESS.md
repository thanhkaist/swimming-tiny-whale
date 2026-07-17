# Progress — Swimming Tiny Whale

Built autonomously in one session, then extended with a leaderboard. Status:
**complete, playable, polished, and tested.** All 73 tests pass; the game runs
cleanly headless and at ~3 ms/frame (comfortably under the 16.6 ms 60-FPS
budget).

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

## Leaderboard feature (added after the initial build)

A local top-10 leaderboard with classic arcade initials entry.

- **Storage** (`storage.py`) — `load_leaderboard` / `save_leaderboard` /
  `qualifies` / `add_score`, stored in `leaderboard.json`. Sorted descending,
  trimmed to 10, tolerant of corrupt/malformed/non-positive entries, and names
  sanitised (uppercase, alnum, clamped to 3). `add_score` returns the new
  board plus the 1-based rank achieved (-1 if it didn't place); ties place the
  newer entry below the incumbent.
- **Flow** — on a qualifying death the game-over panel switches to an inline
  3-slot initials entry (type A–Z/0–9, Backspace, Enter). Submitting saves the
  score and shows the achieved rank. A dedicated `STATE_LEADERBOARD` screen is
  reachable via **L** from both the title and game-over; it slides in, lists
  the board, and highlights the row you just set. Returns to whichever screen
  opened it.
- **Decisions made:** kept the leaderboard in its own file (didn't disturb the
  existing single high-score API/tests); chose 3-letter arcade initials over
  free-text names (robust, on-theme, no text-wrapping/IME concerns); auto-`AAA`
  fallback for an empty entry; clicks don't confirm initials (avoids accidental
  submits). The `#1` high score and the leaderboard are tracked independently
  but stay consistent in normal play.
- **Tests** — 15 storage tests + 7 game-flow integration tests (name-entry
  activation, typing/backspace/cap/submit, no-restart-while-typing, open/leave
  from title and game-over).

## Big update — modes, characters, coins/shop, power-ups, hazards (branch `feature/big-update`)

A large gameplay expansion layered on in dependency-ordered, independently-tested
milestones (one commit each). 151 tests pass; headless smoke + screenshots green.

- **Profile persistence** (`profile.json`): coins, unlocks, selected
  character/mode/trail, per-mode bests — same graceful-degrade JSON pattern as
  the existing high score, with a monkeypatchable path for tests. Non-Normal
  modes get their own `leaderboard_<mode>.json`; Normal keeps `leaderboard.json`.
- **Game modes** (`modes.py`): Zen (no death — clamp instead), Normal, Hard
  (tighter/faster), Daily (deterministic run from the date seed). `gap_for_score`
  / `speed_for_score` stayed single-arg-static compatible via an optional `mode`.
- **Coins & collectibles** (`collectibles.py`): coins spawn in clusters aimed at
  the newest gap, scroll at the *shared* field speed, bank to the profile on
  death and on quit (so Zen still saves). HUD counter.
- **Characters** (`characters.py`): Classic/Coral/Orca/Pip — distinct procedural
  skins *and* feel (gravity/impulse/hitbox scales). Default spec is numerically
  neutral, so the original whale + all physics tests are unchanged.
- **Shop + trails** (`ui.py`, `trails.py`): spend coins to unlock whales and
  cosmetic trails; `ui.py` extracts the shared panel/menu drawing to keep the
  loop thin.
- **Power-ups** (`powerups.py`): Shield/Slow-mo/Magnet/Shrink. Effect timers
  count in **real** frames while the world runs on `dt * time_scale`, so slow-mo
  can't stretch itself. One `_resolve_collision` sink handles Zen-clamp /
  shield-absorb (i-frames + bounce) / death across coral, bounds, and hazards.
- **Hazards** (`hazards.py`) + moving columns: vertically oscillating gaps
  (amplitude capped by band headroom), jellyfish, spiky mines (shield-absorbable),
  and current zones that push the whale. All deterministic from injected RNGs.
- **Screenshot tool**: `python main.py --shot <state> <path> [--frames N]` renders
  any screen headlessly (used to regenerate `docs/`).

**Key correctness guards kept green:** default `WhaleSpec` leaves physics
identical; static `Obstacle` unchanged; `gap_for_score`/`speed_for_score` static
single-arg calls resolve to Normal; existing high-score/leaderboard files
untouched; every new spawner is deterministic from an injected RNG so Daily runs
reproduce and seeded tests pass.

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
