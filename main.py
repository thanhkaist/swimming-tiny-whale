"""Swimming Tiny Whale — entry point, main loop, and state machine.

A thin main loop delegates to ``update()``/``draw()`` on the game object. Three
states — title, playing, game-over — are driven by a small state machine with
smooth cross-fades between them, gentle screen shake and a white flash on
impact. Runs headlessly under ``SDL_VIDEODRIVER=dummy`` for smoke tests.
"""

from __future__ import annotations

import math
import random
import sys

import pygame

import characters
import config
import modes
import powerups
import storage
import trails
import ui
from audio import Audio
from collectibles import CollectibleField
from hazards import HazardField
from obstacles import ObstacleField
from particles import ParticleSystem
from scene import Scene
from util import clamp, ease_out_cubic
from whale import Whale


class Game:
    """Owns all subsystems and the current game state."""

    def __init__(self) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        pygame.display.set_caption(config.CAPTION)
        self.clock = pygame.time.Clock()

        self.rng = random.Random()
        self.audio = Audio()

        self.scene = Scene()
        self.field = ObstacleField(self.rng)
        self.collectibles = CollectibleField(self.rng)
        self.hazards = HazardField(self.rng)
        self.particles = ParticleSystem(self.rng)
        self.effects = powerups.EffectManager()
        self._iframes = 0.0           # invulnerability frames after a shield pop

        self.fonts = self._load_fonts()

        self.state = config.STATE_TITLE
        self.score = 0
        self.new_best = False

        # Player profile: coins, unlocks, selected character/mode/trail.
        self.profile = storage.load_profile()
        self.coins = self.profile["coins"]

        # Whale uses the selected character skin/feel.
        self.whale = Whale(spec=characters.by_id(self.profile["selected_character"]))

        # Active mode for the (next) run + its current best score.
        self.run_mode = modes.by_id(self.profile["selected_mode"])
        self.highscore = self._mode_best(self.run_mode.id)
        self.menu_index = 0           # shared cursor for menu screens
        self.run_coins = 0            # coins collected in the current run
        self._char_previews: dict[str, pygame.Surface] = {}  # skin thumbnails
        self.shop_items: list[dict] = []   # built when the shop opens
        self._trail_timer = 0.0
        self._trail_color_i = 0

        # Leaderboard + arcade-style name entry.
        self.leaderboard = storage.load_leaderboard()
        self.name_entry_active = False       # typing initials on the panel?
        self.entry_initials = ""             # initials typed so far
        self.entry_rank = -1                 # 1-based rank just achieved (-1 none)
        self.leaderboard_return = config.STATE_TITLE  # where to go back to

        # Juice / transition state.
        self.shake = 0.0
        self.flash = 0.0
        self.score_pop = 0.0          # 1→0 timer for the HUD score pop
        self.fade_alpha = 0            # black overlay for state transitions
        self._fade_target = 0
        self._pending_state: str | None = None
        self.state_time = 0.0         # frames spent in the current state
        self.running = True
        self._started = False         # has the player flapped at least once?

    # ------------------------------------------------------------------ #
    # Setup helpers
    # ------------------------------------------------------------------ #
    def _load_fonts(self) -> dict[str, pygame.font.Font]:
        """Load the UI fonts, preferring a rounded/friendly family."""
        pygame.font.init()

        def make(size: int) -> pygame.font.Font:
            match = pygame.font.match_font(config.FONT_NAME, bold=True)
            if match:
                return pygame.font.Font(match, size)
            return pygame.font.SysFont(None, size, bold=True)

        return {
            "huge": make(config.FONT_SIZE_HUGE),
            "large": make(config.FONT_SIZE_LARGE),
            "medium": make(config.FONT_SIZE_MEDIUM),
            "small": make(config.FONT_SIZE_SMALL),
        }

    # ------------------------------------------------------------------ #
    # State transitions
    # ------------------------------------------------------------------ #
    def _begin_transition(self, next_state: str) -> None:
        """Fade to black, then switch to ``next_state`` and fade back in."""
        self._pending_state = next_state
        self._fade_target = 255

    def _enter_state(self, next_state: str) -> None:
        """Immediately switch state and reset per-state bookkeeping."""
        self.state = next_state
        self.state_time = 0.0
        if next_state == config.STATE_PLAYING:
            self.start_run()
        self._fade_target = 0

    def _mode_best(self, mode_id: str) -> int:
        """Best score for ``mode_id`` (Normal uses the legacy high-score file)."""
        if mode_id == config.DEFAULT_MODE:
            return storage.load_highscore()
        return int(self.profile["per_mode_highscores"].get(mode_id, 0))

    def start_run(self) -> None:
        """Reset the world for a fresh run under the selected mode."""
        self.run_mode = modes.by_id(self.profile["selected_mode"])
        self.highscore = self._mode_best(self.run_mode.id)

        # Bank any coins from a prior run that never got persisted.
        self._bank_run_coins()

        # Daily mode is fully deterministic: seed a fresh RNG from today's date
        # so every player gets the same run (coins use a separate stream off the
        # same seed). Other modes vary each attempt.
        if self.run_mode.is_daily:
            base = modes.today_seed()
            run_rng = random.Random(base)
            coin_rng = random.Random(base + 1)
            hazard_rng = random.Random(base + 2)
        else:
            run_rng = random.Random()
            coin_rng = random.Random()
            hazard_rng = random.Random()
        self.field = ObstacleField(run_rng, mode=self.run_mode)
        self.collectibles = CollectibleField(coin_rng, mode=self.run_mode)
        self.hazards = HazardField(hazard_rng, mode=self.run_mode)

        # Rebuild the whale so the run always matches the selected character.
        self.whale = Whale(spec=characters.by_id(self.profile["selected_character"]))
        self.particles.clear()
        self.effects.clear()
        self._iframes = 0.0
        self.score = 0
        self.run_coins = 0
        self.coins = self.profile["coins"]
        self.new_best = False
        self._started = False

    def _bank_run_coins(self) -> None:
        """Persist coins collected this run into the profile balance."""
        if self.run_coins > 0:
            storage.add_coins(self.run_coins)
            self.profile = storage.load_profile()
            self.coins = self.profile["coins"]
            self.run_coins = 0

    # ------------------------------------------------------------------ #
    # Pause / main-menu (instant state swaps — no fade, no run reset)
    # ------------------------------------------------------------------ #
    def _pause(self) -> None:
        """Freeze an in-progress run (keeps all state; resumes exactly here)."""
        if self.state == config.STATE_PLAYING and self._pending_state is None:
            self.state = config.STATE_PAUSED
            self.state_time = 0.0     # drives the overlay pulse

    def _resume(self) -> None:
        """Resume a paused run without resetting anything."""
        if self.state == config.STATE_PAUSED:
            self.state = config.STATE_PLAYING

    def _to_main_menu(self) -> None:
        """Return to the title from game-over (to reach the shop), banking coins."""
        if self._pending_state is None:
            self._bank_run_coins()    # no-op if already banked on death
            self._begin_transition(config.STATE_TITLE)

    # ------------------------------------------------------------------ #
    # Input
    # ------------------------------------------------------------------ #
    def _swim(self) -> None:
        """Handle a swim/confirm input based on current state."""
        if self._pending_state is not None:
            return  # ignore input mid-transition
        if self.state == config.STATE_TITLE:
            self._begin_transition(config.STATE_PLAYING)
        elif self.state == config.STATE_PLAYING:
            self._started = True
            self.whale.swim()
            self.particles.emit_spout(self.whale.spout_origin)
            self.audio.play("swim")
        elif self.state == config.STATE_GAMEOVER:
            if self.state_time > 20:  # small lockout to avoid instant restart
                self._begin_transition(config.STATE_PLAYING)

    def handle_events(self) -> None:
        """Process the input/event queue."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._request_quit()
            elif event.type == pygame.KEYDOWN:
                self._on_keydown(event)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._on_click()

    def _request_quit(self) -> None:
        """Bank any unsaved coins, then ask the loop to stop."""
        self._bank_run_coins()
        self.running = False

    # Menu-style screens (list selection) share one input handler.
    _MENU_STATES = (config.STATE_MODESELECT, config.STATE_CHARSELECT, config.STATE_SHOP)

    def _on_keydown(self, event: pygame.event.Event) -> None:
        """Route a key press based on the current state/sub-mode."""
        # While typing initials, keys go to the name-entry handler exclusively.
        if self.name_entry_active:
            self._handle_name_key(event)
            return

        if event.key == pygame.K_m:
            self.audio.toggle()
            return

        # While paused, the resume keys unfreeze the run; ignore everything else.
        if self.state == config.STATE_PAUSED:
            if event.key in (pygame.K_ESCAPE, pygame.K_p, pygame.K_SPACE,
                             pygame.K_UP, pygame.K_w):
                self._resume()
            return

        # Esc/P pause an in-progress run (Esc no longer quits mid-run).
        if self.state == config.STATE_PLAYING and event.key in (pygame.K_p, pygame.K_ESCAPE):
            self._pause()
            return

        # Esc from game-over returns to the main menu (to visit the shop).
        if self.state == config.STATE_GAMEOVER and event.key == pygame.K_ESCAPE:
            self._to_main_menu()
            return

        # List-selection screens capture all navigation keys.
        if self.state in self._MENU_STATES:
            self._handle_menu_key(event)
            return

        # In the leaderboard view, any key returns to where we came from.
        if self.state == config.STATE_LEADERBOARD:
            self._leave_leaderboard()
            return

        if event.key == pygame.K_l:
            self._open_leaderboard()
            return
        # Menu hotkeys are available from the title screen.
        if self.state == config.STATE_TITLE and event.key == pygame.K_d:
            self._open_menu(config.STATE_MODESELECT)
            return
        if self.state == config.STATE_TITLE and event.key == pygame.K_c:
            self._open_menu(config.STATE_CHARSELECT)
            return
        if self.state == config.STATE_TITLE and event.key == pygame.K_s:
            self._open_menu(config.STATE_SHOP)
            return
        if event.key == pygame.K_ESCAPE:
            self._request_quit()
            return
        if event.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
            self._swim()

    def _on_click(self) -> None:
        """Route a left-click based on the current state/sub-mode."""
        if self.name_entry_active:
            return  # clicks don't confirm initials (avoid accidental submits)
        if self.state == config.STATE_PAUSED:
            self._resume()
            return
        if self.state in self._MENU_STATES:
            self._confirm_menu()
            return
        if self.state == config.STATE_LEADERBOARD:
            self._leave_leaderboard()
            return
        self._swim()

    # ------------------------------------------------------------------ #
    # Leaderboard + name entry
    # ------------------------------------------------------------------ #
    def _open_leaderboard(self) -> None:
        """Show the leaderboard, remembering where to return afterwards."""
        if self._pending_state is not None:
            return
        self.leaderboard = storage.load_leaderboard(mode_id=self.run_mode.id)
        self.leaderboard_return = self.state
        if self.state == config.STATE_TITLE:
            self.entry_rank = -1  # no fresh entry to highlight
        self._begin_transition(config.STATE_LEADERBOARD)

    def _leave_leaderboard(self) -> None:
        """Return from the leaderboard to whichever screen opened it."""
        if self._pending_state is not None:
            return
        self._begin_transition(self.leaderboard_return or config.STATE_TITLE)

    def _handle_name_key(self, event: pygame.event.Event) -> None:
        """Type / erase / confirm the arcade initials on the game-over panel."""
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._submit_name()
        elif event.key == pygame.K_BACKSPACE:
            self.entry_initials = self.entry_initials[:-1]
        else:
            ch = getattr(event, "unicode", "").upper()
            if ch.isalnum() and len(self.entry_initials) < config.INITIALS_LENGTH:
                self.entry_initials += ch

    def _submit_name(self) -> None:
        """Persist the entered initials to the current mode's board; stop editing."""
        name = self.entry_initials or config.DEFAULT_INITIALS
        self.leaderboard, self.entry_rank = storage.add_score(
            name, self.score, mode_id=self.run_mode.id
        )
        self.name_entry_active = False

    # ------------------------------------------------------------------ #
    # Menu screens (mode / character / shop select)
    # ------------------------------------------------------------------ #
    def _open_menu(self, state: str) -> None:
        """Open a list-selection screen, positioning the cursor sensibly."""
        if self._pending_state is not None:
            return
        if state == config.STATE_MODESELECT:
            ids = [m.id for m in modes.MODES]
            self.menu_index = ids.index(self.profile["selected_mode"]) \
                if self.profile["selected_mode"] in ids else 0
        elif state == config.STATE_CHARSELECT:
            ids = [c.id for c in characters.CHARACTERS]
            self.menu_index = ids.index(self.profile["selected_character"]) \
                if self.profile["selected_character"] in ids else 0
        elif state == config.STATE_SHOP:
            self.shop_items = self._build_shop_items()
            self.menu_index = 0
        else:
            self.menu_index = 0
        self._begin_transition(state)

    def _build_shop_items(self) -> list[dict]:
        """Build the current shop listing: locked characters, then trails."""
        items: list[dict] = []
        for spec in characters.CHARACTERS:
            if spec.id not in self.profile["unlocked"]:
                items.append({"kind": "char", "id": spec.id,
                              "name": spec.name, "cost": spec.unlock_cost})
        for tr in trails.TRAILS:
            owned = tr.id in self.profile["unlocked_trails"]
            items.append({"kind": "trail", "id": tr.id, "name": f"{tr.name} trail",
                          "cost": tr.cost, "owned": owned})
        return items

    def _refresh_profile(self) -> None:
        """Reload the profile from disk and re-sync the cached coin balance."""
        self.profile = storage.load_profile()
        self.coins = self.profile["coins"]

    def _menu_length(self) -> int:
        """Number of selectable rows on the current menu screen."""
        if self.state == config.STATE_MODESELECT:
            return len(modes.MODES)
        if self.state == config.STATE_CHARSELECT:
            return len(characters.CHARACTERS)
        if self.state == config.STATE_SHOP:
            return len(self.shop_items)
        return 0

    def _handle_menu_key(self, event: pygame.event.Event) -> None:
        """Navigate / confirm / cancel on a list-selection screen."""
        n = max(1, self._menu_length())
        if event.key in (pygame.K_UP, pygame.K_LEFT, pygame.K_w):
            self.menu_index = (self.menu_index - 1) % n
        elif event.key in (pygame.K_DOWN, pygame.K_RIGHT, pygame.K_s):
            self.menu_index = (self.menu_index + 1) % n
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self._confirm_menu()
        elif event.key in (pygame.K_ESCAPE, pygame.K_b):
            if self._pending_state is None:
                self._begin_transition(config.STATE_TITLE)

    def _confirm_menu(self) -> None:
        """Apply the highlighted selection on the current menu screen."""
        if self._pending_state is not None:
            return
        if self.state == config.STATE_MODESELECT:
            mode = modes.MODES[self.menu_index % len(modes.MODES)]
            self.profile["selected_mode"] = mode.id
            self.run_mode = mode
            storage.set_selected("selected_mode", mode.id)
            self.highscore = self._mode_best(mode.id)
            self._begin_transition(config.STATE_TITLE)
        elif self.state == config.STATE_CHARSELECT:
            spec = characters.CHARACTERS[self.menu_index % len(characters.CHARACTERS)]
            if spec.id in self.profile["unlocked"]:
                self.profile["selected_character"] = spec.id
                storage.set_selected("selected_character", spec.id)
                self.whale = Whale(spec=spec)  # reflect on the title idle
                self._begin_transition(config.STATE_TITLE)
            else:
                # Locked — nudge with a brief flash; unlock happens in the shop.
                self.flash = config.LOCKED_FLASH_ALPHA
        elif self.state == config.STATE_SHOP:
            self._confirm_shop()

    def _confirm_shop(self) -> None:
        """Buy or equip the highlighted shop item."""
        if not self.shop_items:
            return
        item = self.shop_items[self.menu_index % len(self.shop_items)]
        if item["kind"] == "char":
            if storage.spend_coins(item["cost"]):
                storage.unlock_character(item["id"])
                self.audio.play("score")
                self._refresh_profile()
                self.shop_items = self._build_shop_items()
                self.menu_index = min(self.menu_index, max(0, len(self.shop_items) - 1))
            else:
                self.flash = config.LOCKED_FLASH_ALPHA
        else:  # trail
            if item["owned"]:
                storage.set_selected("selected_trail", item["id"])
                self._refresh_profile()
            elif storage.spend_coins(item["cost"]):
                storage.unlock_trail(item["id"])
                storage.set_selected("selected_trail", item["id"])
                self.audio.play("score")
                self._refresh_profile()
                self.shop_items = self._build_shop_items()
            else:
                self.flash = config.LOCKED_FLASH_ALPHA

    # ------------------------------------------------------------------ #
    # Update
    # ------------------------------------------------------------------ #
    def update(self, dt: float) -> None:
        """Advance the whole game by ``dt`` reference-frames."""
        self.state_time += dt
        self.scene.update(dt)
        self._update_transition()
        self._update_juice(dt)

        if self.state == config.STATE_TITLE:
            self._update_title(dt)
        elif self.state == config.STATE_PLAYING:
            self._update_playing(dt)
        elif self.state == config.STATE_PAUSED:
            pass  # gameplay is frozen; only the backdrop/overlay animate
        elif self.state == config.STATE_GAMEOVER:
            self._update_gameover(dt)
        elif self.state in (config.STATE_LEADERBOARD, *self._MENU_STATES):
            self._update_idle(dt)

    def _update_transition(self) -> None:
        """Drive the black-fade cross between states."""
        if self._fade_target > self.fade_alpha:
            self.fade_alpha = min(self._fade_target, self.fade_alpha + config.STATE_FADE_SPEED)
        elif self._fade_target < self.fade_alpha:
            self.fade_alpha = max(self._fade_target, self.fade_alpha - config.STATE_FADE_SPEED)

        # Once fully black and a switch is pending, perform it and fade back.
        if self._pending_state is not None and self.fade_alpha >= 255:
            self._enter_state(self._pending_state)
            self._pending_state = None

    def _update_juice(self, dt: float) -> None:
        """Decay screen shake and impact flash."""
        self.shake *= config.SHAKE_DECAY ** dt
        if self.shake < 0.15:
            self.shake = 0.0
        self.flash = max(0.0, self.flash - config.FLASH_DECAY * dt)
        self.score_pop = max(0.0, self.score_pop - 0.06 * dt)

    def _update_title(self, dt: float) -> None:
        """Idle the whale bobbing on the title screen."""
        self.whale.idle_bob(config.WHALE_START_Y, dt)
        self.particles.update(dt)

    def _update_idle(self, dt: float) -> None:
        """Keep the scene alive on non-gameplay screens (leaderboard/menus)."""
        self.whale.idle_bob(config.WHALE_START_Y, dt)
        self.particles.update(dt)

    def _update_playing(self, dt: float) -> None:
        """Core gameplay tick: physics, obstacles, scoring, collisions."""
        # Before the first flap, the whale hovers so the player can get ready.
        if not self._started:
            self.whale.idle_bob(config.WHALE_START_Y, dt)
            self.particles.update(dt)
            return

        # Timed effects count down in REAL frames; the world runs on a scaled
        # dt so slow-mo lasts a fixed wall-clock time and doesn't stretch itself.
        self.effects.update(dt)
        self._iframes = max(0.0, self._iframes - dt)
        gameplay_dt = dt * self.effects.time_scale

        # Shrink (and the character's own hitbox scale) shrink the collision box.
        self.whale.hitbox_scale = self.whale.spec.hitbox_scale * self.effects.hitbox_scale

        # One scroll speed shared by every field so parallax stays consistent.
        speed = ObstacleField.speed_for_score(self.score, self.run_mode)

        self.whale.update(gameplay_dt)
        gained = self.field.update(self.score, self.whale.x, gameplay_dt)
        if gained:
            self.score += gained
            self.score_pop = 1.0
            self.audio.play("score")
            self.particles.emit_score_pop(self.whale.x, self.whale.y - self.whale.height)

        self._emit_trail(gameplay_dt)
        coins, got_powerups = self.collectibles.update(
            speed, self.whale, self.field, gameplay_dt, effects=self.effects)
        if coins:
            self.run_coins += coins
            self.coins += coins
            self.audio.play("score")
            self.particles.emit_score_pop(self.whale.x + 20, self.whale.y - self.whale.height, "+%d" % coins)
        for kind in got_powerups:
            self.effects.activate(kind)
            self.audio.play("score")
            self.flash = config.LOCKED_FLASH_ALPHA

        hazard_hit = self.hazards.update(
            speed, self.whale, gameplay_dt, effects=self.effects, score=self.score)

        self.particles.update(gameplay_dt)

        lethal = (self.field.collides(self.whale.rect) or self.whale.hits_bounds()
                  or hazard_hit == "hit")
        if self._iframes <= 0 and lethal:
            self._resolve_collision()

    def _emit_trail(self, dt: float) -> None:
        """Leave the selected cosmetic trail behind the whale."""
        trail = trails.by_id(self.profile["selected_trail"])
        if trail.is_none or not trail.colors:
            return
        self._trail_timer -= dt
        if self._trail_timer <= 0:
            self._trail_timer = config.TRAIL_EMIT_INTERVAL
            self._trail_color_i += 1
            color = trail.colors[self._trail_color_i % len(trail.colors)]
            self.particles.emit_trail(
                self.whale.x - self.whale.width * 0.42, self.whale.y + 4, color)

    def _resolve_collision(self) -> None:
        """Decide what a collision means: Zen clamps, a shield absorbs, else die.

        This is the single collision sink for coral, bounds, and hazards, so the
        three outcomes never diverge across subsystems.
        """
        if self.run_mode.no_death:
            self._clamp_whale_to_bounds()
            return
        if self.effects.consume_shield():
            # Absorb the hit: brief invulnerability + a bounce back into play.
            self._iframes = config.SHIELD_IFRAMES
            self.whale.vy = config.SWIM_IMPULSE * 0.8
            self.shake = config.SHAKE_ON_HIT * 0.5
            self.flash = config.LOCKED_FLASH_ALPHA
            self.particles.emit_splash(self.whale.x, self.whale.y)
            self.audio.play("hit")
            return
        self._on_death()

    def _clamp_whale_to_bounds(self) -> None:
        """Keep the whale within the playable band (used by Zen mode)."""
        rect = self.whale.rect
        if rect.top < config.WATER_SURFACE_Y:
            self.whale.y = config.WATER_SURFACE_Y + rect.height / 2
            self.whale.vy = max(0.0, self.whale.vy)
        elif rect.bottom > config.SEABED_Y:
            self.whale.y = config.SEABED_Y - rect.height / 2
            self.whale.vy = min(0.0, self.whale.vy)

    def _update_gameover(self, dt: float) -> None:
        """Let the whale sink to the seabed and particles settle."""
        if self.whale.rect.bottom < config.SEABED_Y:
            self.whale.update(dt)
            if self.whale.rect.bottom > config.SEABED_Y:
                self.whale.y = config.SEABED_Y - self.whale.rect.height / 2
        self.particles.update(dt, spawn_ambient=True)

    def _on_death(self) -> None:
        """Handle a collision: juice, sound, best-score, state change."""
        self.audio.play("hit")
        self.shake = config.SHAKE_ON_HIT
        self.flash = config.FLASH_ON_HIT_ALPHA
        self.particles.emit_splash(self.whale.x, self.whale.y)
        self.whale.alive = False

        # Persist coins earned this run.
        self._bank_run_coins()

        # Record the best score for this mode. Normal keeps the legacy
        # high-score file; other modes record into the profile.
        if self.run_mode.id == config.DEFAULT_MODE:
            self.new_best = self.score > self.highscore
            if self.new_best:
                self.highscore = self.score
                storage.save_highscore(self.highscore)
        else:
            self.new_best = storage.record_mode_score(self.run_mode.id, self.score)
            if self.new_best:
                self.highscore = self.score
                self.profile = storage.load_profile()  # refresh cached bests

        # If the run earns a slot on this mode's leaderboard, enter initials.
        self.entry_rank = -1
        self.entry_initials = ""
        self.name_entry_active = storage.qualifies(self.score, mode_id=self.run_mode.id)

        self.state = config.STATE_GAMEOVER
        self.state_time = 0.0

    # ------------------------------------------------------------------ #
    # Draw
    # ------------------------------------------------------------------ #
    def _shake_offset(self) -> tuple[float, float]:
        """Current random screen-shake offset."""
        if self.shake <= 0:
            return (0.0, 0.0)
        return (
            self.rng.uniform(-self.shake, self.shake),
            self.rng.uniform(-self.shake, self.shake),
        )

    def draw(self) -> None:
        """Render the current frame."""
        offset = self._shake_offset()
        self.scene.draw(self.screen, offset)
        self.field.draw(self.screen, offset)
        self.collectibles.draw(self.screen, offset)
        self.hazards.draw(self.screen, offset)

        # The whale hides during the fully-black part of a title→play fade-in.
        self.whale.draw(self.screen, offset)
        self.particles.draw(self.screen, self.fonts["medium"], offset)

        self.scene.draw_vignette(self.screen)

        if self.state == config.STATE_TITLE:
            self._draw_title()
        elif self.state == config.STATE_PLAYING:
            self._draw_hud()
        elif self.state == config.STATE_PAUSED:
            self._draw_hud()
            self._draw_pause()
        elif self.state == config.STATE_GAMEOVER:
            self._draw_hud()
            self._draw_gameover()
        elif self.state == config.STATE_LEADERBOARD:
            self._draw_leaderboard()
        elif self.state == config.STATE_MODESELECT:
            self._draw_modeselect()
        elif self.state == config.STATE_CHARSELECT:
            self._draw_charselect()
        elif self.state == config.STATE_SHOP:
            self._draw_shop()

        self._draw_flash()
        self._draw_fade()
        self._draw_mute_indicator()
        pygame.display.flip()

    # -- text helpers ---------------------------------------------------- #
    def _text(
        self,
        key: str,
        text: str,
        color: tuple[int, int, int],
        center: tuple[int, int],
        shadow: bool = True,
    ) -> pygame.Rect:
        """Blit centred text with a soft drop shadow; return its rect."""
        font = self.fonts[key]
        if shadow:
            shadow_img = font.render(text, True, config.TEXT_SHADOW)
            srect = shadow_img.get_rect(center=(center[0] + 2, center[1] + 2))
            self.screen.blit(shadow_img, srect)
        img = font.render(text, True, color)
        rect = img.get_rect(center=center)
        self.screen.blit(img, rect)
        return rect

    def _draw_hud(self) -> None:
        """Draw the live score at the top-centre with a pop on each point."""
        cx = config.SCREEN_WIDTH // 2
        cy = 92
        font = self.fonts["huge"]
        text = str(self.score)
        scale = 1.0 + config.SCORE_POP_SCALE * self.score_pop
        shadow = font.render(text, True, config.TEXT_SHADOW)
        base = font.render(text, True, config.TEXT_COLOR)
        if scale != 1.0:
            size = (max(1, int(base.get_width() * scale)), max(1, int(base.get_height() * scale)))
            shadow = pygame.transform.smoothscale(shadow, size)
            base = pygame.transform.smoothscale(base, size)
        self.screen.blit(shadow, shadow.get_rect(center=(cx + 2, cy + 2)))
        self.screen.blit(base, base.get_rect(center=(cx, cy)))

        self._draw_coin_counter()
        self._draw_effect_hud()

        # Before the first flap, gently prompt the player to start.
        if self.state == config.STATE_PLAYING and not self._started:
            pulse = 0.5 + 0.5 * math.sin(self.state_time * 0.12)
            hint = self.fonts["medium"].render("Tap to swim!", True, config.TEXT_COLOR)
            hint.set_alpha(int(120 + 135 * pulse))
            rect = hint.get_rect(center=(cx, config.SCREEN_HEIGHT // 2 + 70))
            self.screen.blit(hint, rect)

    def _draw_effect_hud(self) -> None:
        """Draw active power-up icons with depleting time bars (top-left)."""
        from assets import draw as art

        items = self.effects.hud_items()
        x = 16
        y = 20
        for kind, color, frac in items:
            icon = art.build_powerup(kind, color, 13)
            self.screen.blit(icon, icon.get_rect(midleft=(x, y)))
            # Depleting bar under the icon.
            bar_w = 30
            bx = x + 2
            by = y + 18
            pygame.draw.rect(self.screen, (10, 30, 44), (bx, by, bar_w, 5), border_radius=2)
            pygame.draw.rect(self.screen, color, (bx, by, int(bar_w * frac), 5), border_radius=2)
            x += 44

    def _draw_coin_counter(self, top: int = 22) -> None:
        """Draw a coin icon + live balance in the top-right corner."""
        from assets import draw as art

        coin = art.build_coin(config.COIN_RADIUS)
        label = self.fonts["medium"].render(str(self.coins), True, config.COIN_COLOR)
        right = config.SCREEN_WIDTH - 16
        self.screen.blit(label, label.get_rect(midright=(right, top)))
        self.screen.blit(coin, coin.get_rect(
            midright=(right - label.get_width() - 8, top)))

    def _draw_title(self) -> None:
        """Draw the title screen text with a gentle floating motion."""
        cx = config.SCREEN_WIDTH // 2
        float_y = math.sin(self.state_time * 0.04) * 6
        self._text("huge", "Tiny Whale", config.TEXT_COLOR, (cx, int(150 + float_y)))
        self._text("small", "a swimming adventure", config.TEXT_ACCENT, (cx, 196))

        # Pulsing "tap to swim" prompt.
        pulse = 0.5 + 0.5 * math.sin(self.state_time * 0.08)
        prompt = self.fonts["medium"].render("Tap / Space to swim", True, config.TEXT_COLOR)
        prompt.set_alpha(int(140 + 115 * pulse))
        rect = prompt.get_rect(center=(cx, config.SCREEN_HEIGHT - 210))
        self.screen.blit(prompt, rect)

        self._text("small", f"Mode: {self.run_mode.name}   ·   Best: {self.highscore}",
                   config.TEXT_ACCENT, (cx, config.SCREEN_HEIGHT - 172))
        self._text("small", "D Mode   C Whale   S Shop   L Board", config.TEXT_COLOR,
                   (cx, config.SCREEN_HEIGHT - 140))
        self._text("small", f"{self.coins} coins", config.COIN_COLOR,
                   (cx, config.SCREEN_HEIGHT - 108))

    def _draw_pause(self) -> None:
        """Dim the frozen scene and show a simple resume overlay."""
        cx = config.SCREEN_WIDTH // 2
        overlay = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        overlay.fill((6, 24, 34))
        overlay.set_alpha(config.PAUSE_OVERLAY_ALPHA)
        self.screen.blit(overlay, (0, 0))

        self._text("huge", "Paused", config.TEXT_COLOR, (cx, config.SCREEN_HEIGHT // 2 - 20))
        pulse = 0.5 + 0.5 * math.sin(self.state_time * 0.09)
        prompt = self.fonts["medium"].render("Tap / Space / Esc to resume", True, config.TEXT_COLOR)
        prompt.set_alpha(int(120 + 135 * pulse))
        self.screen.blit(prompt, prompt.get_rect(center=(cx, config.SCREEN_HEIGHT // 2 + 40)))

    def _draw_gameover(self) -> None:
        """Draw the game-over panel: score, best/entry, and either name entry
        or the play-again / leaderboard prompts."""
        cx = config.SCREEN_WIDTH // 2
        # Ease the panel down into place over ~0.5s.
        t = ease_out_cubic(clamp(self.state_time / 30.0, 0.0, 1.0))
        panel_w, panel_h = 320, 248
        panel_y = int(-panel_h + (config.SCREEN_HEIGHT // 2 - panel_h // 2 + panel_h) * t)
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        pygame.draw.rect(panel, (*config.PANEL_COLOR, 235), panel.get_rect(), border_radius=24)
        pygame.draw.rect(panel, (*config.PANEL_BORDER, 255), panel.get_rect(), width=3, border_radius=24)
        prect = panel.get_rect(center=(cx, config.SCREEN_HEIGHT // 2))
        prect.y = panel_y
        self.screen.blit(panel, prect)

        inner_cx = prect.centerx
        self._text("large", "Game Over", config.TEXT_COLOR, (inner_cx, prect.top + 40))
        self._text("medium", f"Score  {self.score}", config.TEXT_COLOR, (inner_cx, prect.top + 92))

        if self.name_entry_active:
            self._draw_name_entry(prect)
            return

        # Post-entry / non-qualifying: show best or achieved rank, then prompts.
        if self.entry_rank > 0:
            label = "New High Score!" if self.new_best else f"Ranked #{self.entry_rank}!"
            rect = self._text("medium", label, config.TEXT_ACCENT, (inner_cx, prect.top + 132))
            self._draw_new_best_sparkles(rect)
        else:
            best_label = f"Best  {self.highscore}"
            self._text("medium", best_label, config.TEXT_COLOR, (inner_cx, prect.top + 132))

        if self.state_time > 20:
            pulse = 0.5 + 0.5 * math.sin(self.state_time * 0.09)
            prompt = self.fonts["small"].render("Tap / Space to play again", True, config.TEXT_COLOR)
            prompt.set_alpha(int(120 + 135 * pulse))
            self.screen.blit(prompt, prompt.get_rect(center=(inner_cx, prect.bottom - 44)))
            self._text("small", "L  Board      ·      Esc  Menu", config.TEXT_ACCENT,
                       (inner_cx, prect.bottom - 20))

    def _draw_name_entry(self, prect: pygame.Rect) -> None:
        """Draw the arcade initials-entry UI inside the game-over panel."""
        inner_cx = prect.centerx
        heading = "New High Score!" if self.new_best else "You made the board!"
        self._text("small", heading, config.TEXT_ACCENT, (inner_cx, prect.top + 128))

        # Three character slots; the active slot blinks with a caret.
        slots = config.INITIALS_LENGTH
        box_w, box_h, gap = 46, 54, 12
        total = slots * box_w + (slots - 1) * gap
        start_x = inner_cx - total // 2
        top = prect.top + 148
        blink = (int(self.state_time / 16) % 2) == 0
        for i in range(slots):
            bx = start_x + i * (box_w + gap)
            rect = pygame.Rect(bx, top, box_w, box_h)
            active = i == len(self.entry_initials)
            border = config.TEXT_ACCENT if active else config.PANEL_BORDER
            pygame.draw.rect(self.screen, (10, 40, 56), rect, border_radius=10)
            pygame.draw.rect(self.screen, border, rect, width=3, border_radius=10)
            ch = self.entry_initials[i] if i < len(self.entry_initials) else ""
            if ch:
                self._text("large", ch, config.TEXT_COLOR, rect.center, shadow=False)
            elif active and blink:
                self._text("large", "_", config.TEXT_ACCENT, (rect.centerx, rect.centery + 6),
                           shadow=False)

        self._text("small", "Type A–Z / 0–9  ·  Enter to save",
                   config.TEXT_COLOR, (inner_cx, prect.bottom - 24))

    def _draw_new_best_sparkles(self, around: pygame.Rect) -> None:
        """Draw twinkling 4-point sparkles flanking the 'New Best!' label."""
        spots = [
            (around.left - 16, around.centery - 6),
            (around.right + 16, around.centery + 4),
            (around.left - 2, around.top - 8),
            (around.right + 2, around.bottom + 4),
        ]
        for i, (sx, sy) in enumerate(spots):
            tw = 0.5 + 0.5 * math.sin(self.state_time * 0.16 + i * 1.6)
            size = 4 + 4 * tw
            alpha = int(120 + 135 * tw)
            color = (*config.TEXT_ACCENT, alpha)
            spark = pygame.Surface((int(size * 2 + 2), int(size * 2 + 2)), pygame.SRCALPHA)
            c = spark.get_width() / 2
            pygame.draw.line(spark, color, (c, c - size), (c, c + size), 2)
            pygame.draw.line(spark, color, (c - size, c), (c + size, c), 2)
            pygame.draw.line(spark, color, (c - size * 0.5, c - size * 0.5),
                             (c + size * 0.5, c + size * 0.5), 1)
            pygame.draw.line(spark, color, (c - size * 0.5, c + size * 0.5),
                             (c + size * 0.5, c - size * 0.5), 1)
            self.screen.blit(spark, spark.get_rect(center=(sx, sy)))

    def _draw_leaderboard(self) -> None:
        """Draw the ranked top-scores panel with an eased slide-in."""
        prect = ui.slide_panel(self.screen, self.state_time, 360, 540)
        inner_cx = prect.centerx
        self._text("large", "Leaderboard", config.TEXT_ACCENT, (inner_cx, prect.top + 36))
        self._text("small", f"{self.run_mode.name} mode", config.TEXT_COLOR,
                   (inner_cx, prect.top + 68))

        left = prect.left + 30
        right = prect.right - 30
        row_top = prect.top + 104
        row_h = 40

        if not self.leaderboard:
            self._text("small", "No scores yet —", config.TEXT_COLOR,
                       (inner_cx, prect.top + 200))
            self._text("small", "be the first!", config.TEXT_COLOR,
                       (inner_cx, prect.top + 228))
        else:
            for i, entry in enumerate(self.leaderboard):
                y = row_top + i * row_h
                is_me = (i + 1) == self.entry_rank
                color = config.TEXT_ACCENT if is_me else config.TEXT_COLOR
                if is_me:
                    ui.highlight_row(self.screen, pygame.Rect(
                        left - 8, y - row_h // 2, right - left + 16, row_h - 6), radius=8)
                self._text("medium", f"{i + 1}", color, (left + 12, y), shadow=False)
                name_img = self.fonts["medium"].render(entry["name"], True, color)
                self.screen.blit(name_img, name_img.get_rect(midleft=(left + 52, y)))
                score_img = self.fonts["medium"].render(str(entry["score"]), True, color)
                self.screen.blit(score_img, score_img.get_rect(midright=(right - 6, y)))

        pulse = 0.5 + 0.5 * math.sin(self.state_time * 0.09)
        back = self.fonts["small"].render("Tap / Space to return", True, config.TEXT_COLOR)
        back.set_alpha(int(120 + 135 * pulse))
        self.screen.blit(back, back.get_rect(center=(inner_cx, prect.bottom - 26)))

    def _draw_modeselect(self) -> None:
        """Draw the mode-selection panel with per-mode bests and a cursor."""
        prect = ui.slide_panel(self.screen, self.state_time, 380, 470)
        inner_cx = prect.centerx
        self._text("large", "Select Mode", config.TEXT_ACCENT, (inner_cx, prect.top + 42))

        left = prect.left + 26
        right = prect.right - 26
        row_top = prect.top + 108
        row_h = 78
        for i, mode in enumerate(modes.MODES):
            y = row_top + i * row_h
            selected = i == self.menu_index
            color = config.TEXT_ACCENT if selected else config.TEXT_COLOR
            if selected:
                ui.highlight_row(self.screen, pygame.Rect(
                    left - 8, y - row_h // 2 + 6, right - left + 16, row_h - 12))
            equipped = mode.id == self.profile["selected_mode"]
            name = ("* " if equipped else "") + mode.name
            name_img = self.fonts["medium"].render(name, True, color)
            self.screen.blit(name_img, name_img.get_rect(midleft=(left + 6, y - 14)))
            best_img = self.fonts["small"].render(f"best {self._mode_best(mode.id)}", True, color)
            self.screen.blit(best_img, best_img.get_rect(midright=(right - 4, y - 14)))
            tag_img = self.fonts["small"].render(mode.tagline, True, config.TEXT_COLOR)
            tag_img.set_alpha(200 if selected else 130)
            self.screen.blit(tag_img, tag_img.get_rect(midleft=(left + 6, y + 14)))

        self._text("small", "Up/Down choose   ·   Enter select   ·   Esc back",
                   config.TEXT_COLOR, (inner_cx, prect.bottom - 24))

    def _char_preview(self, spec: "characters.WhaleSpec") -> pygame.Surface:
        """Return a cached small whale thumbnail for ``spec``."""
        cached = self._char_previews.get(spec.id)
        if cached is None:
            from assets import draw as art
            base = art.build_whale_surface(0.0, spec)
            scale = 0.8
            cached = pygame.transform.smoothscale(
                base, (int(base.get_width() * scale), int(base.get_height() * scale)))
            self._char_previews[spec.id] = cached
        return cached

    def _draw_charselect(self) -> None:
        """Draw the character carousel with previews, feel, and lock/cost."""
        prect = ui.slide_panel(self.screen, self.state_time, 400, 500)
        inner_cx = prect.centerx
        self._text("large", "Whales", config.TEXT_ACCENT, (inner_cx, prect.top + 40))

        left = prect.left + 24
        right = prect.right - 24
        row_top = prect.top + 104
        row_h = 84
        for i, spec in enumerate(characters.CHARACTERS):
            y = row_top + i * row_h
            selected = i == self.menu_index
            unlocked = spec.id in self.profile["unlocked"]
            color = config.TEXT_ACCENT if selected else config.TEXT_COLOR
            if selected:
                ui.highlight_row(self.screen, pygame.Rect(
                    left - 6, y - row_h // 2 + 6, right - left + 12, row_h - 12))
            # Whale thumbnail (dimmed if locked).
            thumb = self._char_preview(spec)
            if not unlocked:
                thumb = thumb.copy()
                thumb.fill((90, 90, 90, 255), special_flags=pygame.BLEND_RGBA_MULT)
            self.screen.blit(thumb, thumb.get_rect(center=(left + 40, y)))
            # Name + equipped marker.
            equipped = spec.id == self.profile["selected_character"]
            name = ("* " if equipped else "") + spec.name
            name_img = self.fonts["medium"].render(name, True, color)
            self.screen.blit(name_img, name_img.get_rect(midleft=(left + 88, y - 14)))
            tag_img = self.fonts["small"].render(spec.tagline, True, config.TEXT_COLOR)
            tag_img.set_alpha(200 if selected else 130)
            self.screen.blit(tag_img, tag_img.get_rect(midleft=(left + 88, y + 14)))
            # Right side: locked cost, or "owned".
            if unlocked:
                status, scol = "owned", config.TEXT_COLOR
            else:
                status, scol = f"{spec.unlock_cost} coins", config.COIN_COLOR
            st_img = self.fonts["small"].render(status, True, scol)
            self.screen.blit(st_img, st_img.get_rect(midright=(right - 4, y - 14)))

        self._text("small", "Up/Down choose   ·   Enter select   ·   Esc back",
                   config.TEXT_COLOR, (inner_cx, prect.bottom - 22))

    def _draw_shop(self) -> None:
        """Draw the shop: coin balance, buyable characters, and trails."""
        prect = ui.slide_panel(self.screen, self.state_time, 400, 520)
        inner_cx = prect.centerx
        self._text("large", "Shop", config.TEXT_ACCENT, (inner_cx, prect.top + 38))
        self._text("small", f"{self.coins} coins", config.COIN_COLOR,
                   (inner_cx, prect.top + 72))

        left = prect.left + 26
        right = prect.right - 26
        row_top = prect.top + 116
        row_h = 46
        for i, item in enumerate(self.shop_items):
            y = row_top + i * row_h
            selected = i == self.menu_index
            color = config.TEXT_ACCENT if selected else config.TEXT_COLOR
            if selected:
                ui.highlight_row(self.screen, pygame.Rect(
                    left - 8, y - row_h // 2 + 4, right - left + 16, row_h - 8))
            equipped = (item["kind"] == "trail"
                        and item["id"] == self.profile["selected_trail"])
            name = ("* " if equipped else "") + item["name"]
            name_img = self.fonts["medium"].render(name, True, color)
            self.screen.blit(name_img, name_img.get_rect(midleft=(left + 4, y)))
            # Right side: price to buy, or owned/equip state.
            if item["kind"] == "trail" and item["owned"]:
                status, scol = ("equipped" if equipped else "equip"), config.TEXT_COLOR
            else:
                status, scol = f"{item['cost']}", config.COIN_COLOR
            st_img = self.fonts["small"].render(status, True, scol)
            self.screen.blit(st_img, st_img.get_rect(midright=(right - 2, y)))

        if not self.shop_items:
            self._text("small", "Everything unlocked!", config.TEXT_COLOR,
                       (inner_cx, prect.centery))
        self._text("small", "Enter buy/equip   ·   Esc back",
                   config.TEXT_COLOR, (inner_cx, prect.bottom - 22))

    def _draw_flash(self) -> None:
        """White impact flash overlay."""
        if self.flash <= 0:
            return
        overlay = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        overlay.fill((255, 255, 255))
        overlay.set_alpha(int(self.flash))
        self.screen.blit(overlay, (0, 0))

    def _draw_fade(self) -> None:
        """Black transition overlay."""
        if self.fade_alpha <= 0:
            return
        overlay = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        overlay.fill((4, 20, 30))
        overlay.set_alpha(int(self.fade_alpha))
        self.screen.blit(overlay, (0, 0))

    def _draw_mute_indicator(self) -> None:
        """Small muted/‘no audio’ hint in the corner."""
        if self.audio.available and self.audio.enabled:
            return
        label = "muted (M)" if self.audio.available else "no audio"
        img = self.fonts["small"].render(label, True, config.TEXT_COLOR)
        img.set_alpha(120)
        self.screen.blit(img, (10, config.SCREEN_HEIGHT - 28))

    # ------------------------------------------------------------------ #
    # Main loop
    # ------------------------------------------------------------------ #
    def run(self, max_frames: int | None = None) -> None:
        """Run the main loop. ``max_frames`` bounds it for headless smoke tests."""
        frames = 0
        while self.running:
            dt_ms = self.clock.tick(config.FPS)
            # Normalise to reference frames; clamp to avoid spiral-of-death on lag.
            dt = clamp(dt_ms / (1000.0 / config.REFERENCE_FPS), 0.0, 2.5)

            self.handle_events()
            self.update(dt)
            self.draw()

            frames += 1
            if max_frames is not None and frames >= max_frames:
                break


def _arg_after(flag: str, default: str | None = None) -> str | None:
    """Return the CLI argument following ``flag`` (or ``default``)."""
    if flag in sys.argv:
        try:
            return sys.argv[sys.argv.index(flag) + 1]
        except IndexError:
            return default
    return default


def shot(state: str, path: str, frames: int = 60) -> None:
    """Render ``state`` for ``frames`` and save a PNG (headless screenshot tool).

    Seeds a representative scene for gameplay states (a run in progress with a
    coin, a power-up, and a hazard) so screenshots show the features off.
    """
    game = Game()
    if state == config.STATE_PLAYING:
        import powerups
        from collectibles import Coin, PowerUp
        from hazards import Jellyfish
        game.start_run()
        game.state = config.STATE_PLAYING
        game._started = True
        game.coins = 128
        game.score = 6
        game.effects.activate(powerups.MAGNET)
        # Advance the world while steering the whale through the gaps so the
        # scene fills with columns (never dies), then stage props around it.
        for _ in range(frames):
            ahead = [o for o in game.field.obstacles if o.center_x >= game.whale.x - 20]
            if ahead:
                game.whale.y = ahead[0].gap_center
                game.whale.vy = -2
            game.scene.update(1.0)
            game.field.update(game.score, game.whale.x + 9999, 1.0)
            game.particles.update(1.0)
        wy = game.whale.y
        game.collectibles.items = [Coin(game.whale.x + 150, wy - 10),
                                   PowerUp(game.whale.x + 250, wy + 40, powerups.SHIELD)]
        game.hazards.hazards = [Jellyfish(game.whale.x + 210, wy - 90, game.rng)]
    elif state in game._MENU_STATES:
        game._open_menu(state)
        for _ in range(frames):
            game.update(1.0)
    else:
        game.state = state
        for _ in range(frames):
            game.update(1.0)
    game.draw()
    pygame.image.save(game.screen, path)


def main() -> None:
    """Program entry point."""
    # Headless screenshot: `python main.py --shot <state> <path> [--frames N]`.
    if "--shot" in sys.argv:
        state = _arg_after("--shot", config.STATE_TITLE) or config.STATE_TITLE
        idx = sys.argv.index("--shot")
        path = sys.argv[idx + 2] if len(sys.argv) > idx + 2 else "shot.png"
        frames = int(_arg_after("--frames", "60") or "60")
        shot(state, path, frames)
        pygame.quit()
        return

    game = Game()
    # Allow a bounded, self-exiting smoke run: `... python main.py --frames 120`.
    max_frames: int | None = None
    if "--frames" in sys.argv:
        try:
            max_frames = int(sys.argv[sys.argv.index("--frames") + 1])
        except (ValueError, IndexError):
            max_frames = 120
    game.run(max_frames=max_frames)
    pygame.quit()


if __name__ == "__main__":
    main()
