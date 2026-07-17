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
        self.whale = Whale()
        self.field = ObstacleField(self.rng)
        self.particles = ParticleSystem(self.rng)

        self.fonts = self._load_fonts()

        self.state = config.STATE_TITLE
        self.score = 0
        self.highscore = storage.load_highscore()
        self.new_best = False

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
                if event.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
                    self._swim()
                elif event.key == pygame.K_m:
                    self.audio.toggle()
                elif event.key == pygame.K_ESCAPE:
                    self.running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._swim()

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

    def _draw_gameover(self) -> None:
        """Draw the game-over panel with an eased slide-in."""
        cx = config.SCREEN_WIDTH // 2
        # Ease the panel down into place over ~0.5s.
        t = ease_out_cubic(clamp(self.state_time / 30.0, 0.0, 1.0))
        panel_w, panel_h = 320, 220
        panel_y = int(-panel_h + (config.SCREEN_HEIGHT // 2 - panel_h // 2 + panel_h) * t)
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        pygame.draw.rect(panel, (*config.PANEL_COLOR, 235), panel.get_rect(), border_radius=24)
        pygame.draw.rect(panel, (*config.PANEL_BORDER, 255), panel.get_rect(), width=3, border_radius=24)
        prect = panel.get_rect(center=(cx, config.SCREEN_HEIGHT // 2))
        prect.y = panel_y
        self.screen.blit(panel, prect)

        inner_cx = prect.centerx
        self._text("large", "Game Over", config.TEXT_COLOR, (inner_cx, prect.top + 44))
        self._text("medium", f"Score  {self.score}", config.TEXT_COLOR, (inner_cx, prect.top + 100))
        best_label = "New Best!  " + str(self.highscore) if self.new_best else f"Best  {self.highscore}"
        best_color = config.TEXT_ACCENT if self.new_best else config.TEXT_COLOR
        self._text("medium", best_label, best_color, (inner_cx, prect.top + 138))

        if self.state_time > 20:
            pulse = 0.5 + 0.5 * math.sin(self.state_time * 0.09)
            prompt = self.fonts["small"].render("Tap / Space to play again", True, config.TEXT_COLOR)
            prompt.set_alpha(int(120 + 135 * pulse))
            rect = prompt.get_rect(center=(inner_cx, prect.bottom - 26))
            self.screen.blit(prompt, rect)

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
