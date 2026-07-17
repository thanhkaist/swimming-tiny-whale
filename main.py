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

import config
import storage
from audio import Audio
from obstacles import ObstacleField
from particles import ParticleSystem
from scene import Scene
from util import clamp, ease_out_cubic, lerp
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
        self.whale = Whale()
        self.field = ObstacleField(self.rng)
        self.particles = ParticleSystem(self.rng)

        self.fonts = self._load_fonts()

        self.state = config.STATE_TITLE
        self.score = 0
        self.highscore = storage.load_highscore()
        self.new_best = False

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

    def start_run(self) -> None:
        """Reset the world for a fresh run."""
        self.whale.reset()
        self.field.reset()
        self.particles.clear()
        self.score = 0
        self.new_best = False
        self._started = False

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
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self._on_keydown(event)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._on_click()

    def _on_keydown(self, event: pygame.event.Event) -> None:
        """Route a key press based on the current state/sub-mode."""
        # While typing initials, keys go to the name-entry handler exclusively.
        if self.name_entry_active:
            self._handle_name_key(event)
            return

        if event.key == pygame.K_m:
            self.audio.toggle()
            return

        # In the leaderboard view, any key returns to where we came from.
        if self.state == config.STATE_LEADERBOARD:
            self._leave_leaderboard()
            return

        if event.key == pygame.K_l:
            self._open_leaderboard()
            return
        if event.key == pygame.K_ESCAPE:
            self.running = False
            return
        if event.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
            self._swim()

    def _on_click(self) -> None:
        """Route a left-click based on the current state/sub-mode."""
        if self.name_entry_active:
            return  # clicks don't confirm initials (avoid accidental submits)
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
        self.leaderboard = storage.load_leaderboard()
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
        """Persist the entered initials to the leaderboard and stop editing."""
        name = self.entry_initials or config.DEFAULT_INITIALS
        self.leaderboard, self.entry_rank = storage.add_score(name, self.score)
        self.name_entry_active = False

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
        elif self.state == config.STATE_GAMEOVER:
            self._update_gameover(dt)
        elif self.state == config.STATE_LEADERBOARD:
            self._update_leaderboard(dt)

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

    def _update_leaderboard(self, dt: float) -> None:
        """Keep the scene alive while viewing the leaderboard."""
        self.whale.idle_bob(config.WHALE_START_Y, dt)
        self.particles.update(dt)

    def _update_playing(self, dt: float) -> None:
        """Core gameplay tick: physics, obstacles, scoring, collisions."""
        # Before the first flap, the whale hovers so the player can get ready.
        if not self._started:
            self.whale.idle_bob(config.WHALE_START_Y, dt)
            self.particles.update(dt)
            return

        self.whale.update(dt)
        gained = self.field.update(self.score, self.whale.x, dt)
        if gained:
            self.score += gained
            self.score_pop = 1.0
            self.audio.play("score")
            self.particles.emit_score_pop(self.whale.x, self.whale.y - self.whale.height)
        self.particles.update(dt)

        if self.field.collides(self.whale.rect) or self.whale.hits_bounds():
            self._on_death()

    def _update_gameover(self, dt: float) -> None:
        """Let the whale sink to the seabed and particles settle."""
        if self.whale.rect.bottom < config.SEABED_Y:
            self.whale.update(dt)
            if self.whale.rect.bottom > config.SEABED_Y:
                self.whale.y = config.SEABED_Y - self.whale.rect.height / 2
        self.particles.update(dt, spawn_ambient=True)

    def _on_death(self) -> None:
        """Handle a collision: juice, sound, high-score, state change."""
        self.audio.play("hit")
        self.shake = config.SHAKE_ON_HIT
        self.flash = config.FLASH_ON_HIT_ALPHA
        self.particles.emit_splash(self.whale.x, self.whale.y)
        self.whale.alive = False

        if self.score > self.highscore:
            self.highscore = self.score
            self.new_best = True
            storage.save_highscore(self.highscore)

        # If the run earns a leaderboard slot, start arcade initials entry.
        self.entry_rank = -1
        self.entry_initials = ""
        self.name_entry_active = storage.qualifies(self.score)

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

        # The whale hides during the fully-black part of a title→play fade-in.
        self.whale.draw(self.screen, offset)
        self.particles.draw(self.screen, self.fonts["medium"], offset)

        self.scene.draw_vignette(self.screen)

        if self.state == config.STATE_TITLE:
            self._draw_title()
        elif self.state == config.STATE_PLAYING:
            self._draw_hud()
        elif self.state == config.STATE_GAMEOVER:
            self._draw_hud()
            self._draw_gameover()
        elif self.state == config.STATE_LEADERBOARD:
            self._draw_leaderboard()

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

        # Before the first flap, gently prompt the player to start.
        if self.state == config.STATE_PLAYING and not self._started:
            pulse = 0.5 + 0.5 * math.sin(self.state_time * 0.12)
            hint = self.fonts["medium"].render("Tap to swim!", True, config.TEXT_COLOR)
            hint.set_alpha(int(120 + 135 * pulse))
            rect = hint.get_rect(center=(cx, config.SCREEN_HEIGHT // 2 + 70))
            self.screen.blit(hint, rect)

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

        self._text("small", f"Best: {self.highscore}", config.TEXT_ACCENT,
                   (cx, config.SCREEN_HEIGHT - 160))
        self._text("small", "L  ·  Leaderboard", config.TEXT_COLOR,
                   (cx, config.SCREEN_HEIGHT - 128))

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
            self.screen.blit(prompt, prompt.get_rect(center=(inner_cx, prect.bottom - 46)))
            self._text("small", "L  ·  Leaderboard", config.TEXT_ACCENT,
                       (inner_cx, prect.bottom - 22))

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
        cx = config.SCREEN_WIDTH // 2
        t = ease_out_cubic(clamp(self.state_time / 26.0, 0.0, 1.0))
        panel_w, panel_h = 360, 540
        target_y = config.SCREEN_HEIGHT // 2 - panel_h // 2
        panel_y = int(lerp(-panel_h, target_y, t))

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        pygame.draw.rect(panel, (*config.PANEL_COLOR, 238), panel.get_rect(), border_radius=26)
        pygame.draw.rect(panel, (*config.PANEL_BORDER, 255), panel.get_rect(), width=3, border_radius=26)
        prect = panel.get_rect(center=(cx, config.SCREEN_HEIGHT // 2))
        prect.y = panel_y
        self.screen.blit(panel, prect)

        inner_cx = prect.centerx
        self._text("large", "Leaderboard", config.TEXT_ACCENT, (inner_cx, prect.top + 40))

        left = prect.left + 30
        right = prect.right - 30
        row_top = prect.top + 86
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
                    hl = pygame.Rect(left - 8, y - row_h // 2, right - left + 16, row_h - 6)
                    hi = pygame.Surface(hl.size, pygame.SRCALPHA)
                    hi.fill((*config.PANEL_BORDER, 46))
                    self.screen.blit(hi, hl)
                self._text("medium", f"{i + 1}", color, (left + 12, y), shadow=False)
                name_img = self.fonts["medium"].render(entry["name"], True, color)
                self.screen.blit(name_img, name_img.get_rect(midleft=(left + 52, y)))
                score_img = self.fonts["medium"].render(str(entry["score"]), True, color)
                self.screen.blit(score_img, score_img.get_rect(midright=(right - 6, y)))

        pulse = 0.5 + 0.5 * math.sin(self.state_time * 0.09)
        back = self.fonts["small"].render("Tap / Space to return", True, config.TEXT_COLOR)
        back.set_alpha(int(120 + 135 * pulse))
        self.screen.blit(back, back.get_rect(center=(inner_cx, prect.bottom - 26)))

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


def main() -> None:
    """Program entry point."""
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
