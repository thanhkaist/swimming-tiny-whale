"""Central configuration for Swimming Tiny Whale.

Every tunable value in the game lives here as a named constant so that no
other module contains a magic number. Grouped by concern: window/timing,
physics, obstacles, whale, particles, scene, colors, and UI.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# Window & timing
# --------------------------------------------------------------------------- #
SCREEN_WIDTH: int = 480
SCREEN_HEIGHT: int = 720
FPS: int = 60
CAPTION: str = "Swimming Tiny Whale"

# Logical timestep. We update using dt normalised so that 1.0 == one frame at
# the target FPS, keeping the physics feel identical to classic Flappy Bird
# while still being frame-rate independent.
REFERENCE_FPS: float = 60.0

# --------------------------------------------------------------------------- #
# Physics (whale movement)
# --------------------------------------------------------------------------- #
# Downward acceleration applied every frame (pixels / frame^2 at REFERENCE_FPS).
GRAVITY: float = 0.45
# Instant upward velocity set when the player swims (negative == up).
SWIM_IMPULSE: float = -7.6
# Clamp so the whale never falls or rockets faster than these.
MAX_FALL_SPEED: float = 11.0
MAX_RISE_SPEED: float = -10.0

# --------------------------------------------------------------------------- #
# World boundaries
# --------------------------------------------------------------------------- #
WATER_SURFACE_Y: int = 46          # Top boundary (the shimmering surface).
SEABED_Y: int = SCREEN_HEIGHT - 54  # Bottom boundary (the sandy floor).

# --------------------------------------------------------------------------- #
# Whale entity
# --------------------------------------------------------------------------- #
WHALE_START_X: int = 132
WHALE_START_Y: int = SCREEN_HEIGHT // 2
WHALE_WIDTH: int = 66
WHALE_HEIGHT: int = 44
# Collision hitbox is a little smaller than the art for a forgiving feel.
WHALE_HITBOX_SHRINK_X: int = 12
WHALE_HITBOX_SHRINK_Y: int = 10

# Tilt: whale rotates toward its velocity. Degrees.
WHALE_MAX_TILT_UP: float = 24.0
WHALE_MAX_TILT_DOWN: float = -70.0
WHALE_TILT_EASING: float = 0.15    # How quickly the drawn tilt approaches target.
WHALE_TILT_VELOCITY_SCALE: float = 5.0  # Velocity → degrees mapping divisor.

# Idle bob (only on the title screen / before first flap).
WHALE_BOB_AMPLITUDE: float = 8.0
WHALE_BOB_SPEED: float = 0.05
# Tail flap animation speed (radians per frame accumulation).
WHALE_TAIL_FLAP_SPEED: float = 0.22
WHALE_TAIL_FLAP_SWIM_BOOST: float = 0.9  # Extra flap energy right after a swim.

# --------------------------------------------------------------------------- #
# Obstacles (coral / seaweed columns)
# --------------------------------------------------------------------------- #
OBSTACLE_WIDTH: int = 84
OBSTACLE_GAP_START: int = 220      # Vertical gap at the start (easy).
OBSTACLE_GAP_MIN: int = 158        # Gap never shrinks below this (hard cap).
OBSTACLE_GAP_SHRINK_PER_POINT: float = 2.2  # Gap tightens as score rises.
OBSTACLE_SPACING: int = 260        # Horizontal distance between columns.
OBSTACLE_SPEED_START: float = 2.6  # Initial scroll speed (px/frame).
OBSTACLE_SPEED_MAX: float = 5.2
OBSTACLE_SPEED_RAMP_PER_POINT: float = 0.06
# Vertical margin so gaps never hug the surface or seabed.
OBSTACLE_EDGE_MARGIN: int = 70
# First obstacle appears this far to the right of the screen edge.
OBSTACLE_FIRST_OFFSET: int = 120

# --------------------------------------------------------------------------- #
# Particles
# --------------------------------------------------------------------------- #
BUBBLE_SPAWN_CHANCE: float = 0.18   # Per-frame chance of an ambient bubble.
BUBBLE_MIN_RADIUS: int = 2
BUBBLE_MAX_RADIUS: int = 7
BUBBLE_RISE_SPEED_MIN: float = 0.4
BUBBLE_RISE_SPEED_MAX: float = 1.6
BUBBLE_WOBBLE_AMPLITUDE: float = 0.8
BUBBLE_LIFETIME: int = 260          # Frames before an ambient bubble fades.

SPOUT_BUBBLE_COUNT: int = 9         # Bubbles emitted per swim (the "spout").
SPOUT_SPEED_MIN: float = 0.8
SPOUT_SPEED_MAX: float = 2.6

SPLASH_PARTICLE_COUNT: int = 26     # Burst on collision.
SPLASH_SPEED_MIN: float = 2.0
SPLASH_SPEED_MAX: float = 7.5
SPLASH_GRAVITY: float = 0.18
SPLASH_LIFETIME: int = 46

SCORE_POP_LIFETIME: int = 42        # Frames the "+1" pop lingers.
SCORE_POP_RISE: float = 1.1

# --------------------------------------------------------------------------- #
# Scene / background
# --------------------------------------------------------------------------- #
GODRAY_COUNT: int = 5
GODRAY_SPEED: float = 0.0016        # Sway speed of the light shafts.
GODRAY_MAX_ALPHA: int = 42
GODRAY_TOP_WIDTH: int = 22          # Beam width at the surface.
GODRAY_BOTTOM_WIDTH: int = 64       # Beam width where it fades out in the deep.
GODRAY_SWAY_PX: float = 26.0        # Horizontal sway amplitude of each beam.

PLANKTON_COUNT: int = 46            # Drifting specks in the mid layer.
PLANKTON_DRIFT_SPEED: float = 0.25

FAR_FISH_COUNT: int = 6             # Distant parallax fish silhouettes.
FAR_FISH_SPEED_MIN: float = 0.3
FAR_FISH_SPEED_MAX: float = 0.7

PARALLAX_KELP_COUNT: int = 7        # Background kelp fronds (slow parallax).
PARALLAX_KELP_SPEED: float = 0.6

# --------------------------------------------------------------------------- #
# Juice / feel
# --------------------------------------------------------------------------- #
SHAKE_ON_HIT: float = 16.0          # Initial screen-shake magnitude (px).
SHAKE_DECAY: float = 0.86           # Per-frame shake damping.
FLASH_ON_HIT_ALPHA: int = 130       # White flash alpha on collision.
FLASH_DECAY: int = 8                # Flash alpha reduction per frame.
STATE_FADE_SPEED: int = 22          # Alpha step for screen transitions.
VIGNETTE_STRENGTH: int = 115        # Max corner darkening alpha (0 disables).
SCORE_POP_SCALE: float = 0.42       # Extra scale of the HUD number on a point.

# --------------------------------------------------------------------------- #
# Colors (RGB)  — soft underwater palette
# --------------------------------------------------------------------------- #
# Vertical gradient endpoints: deep teal (bottom) → bright aqua (top).
GRADIENT_TOP: tuple[int, int, int] = (86, 205, 214)     # bright aqua
GRADIENT_BOTTOM: tuple[int, int, int] = (11, 58, 82)    # deep teal

SURFACE_COLOR: tuple[int, int, int] = (168, 240, 245)
SURFACE_HIGHLIGHT: tuple[int, int, int] = (222, 253, 255)
SEABED_COLOR: tuple[int, int, int] = (196, 176, 122)
SEABED_DARK: tuple[int, int, int] = (150, 130, 86)

GODRAY_COLOR: tuple[int, int, int] = (215, 250, 255)
PLANKTON_COLOR: tuple[int, int, int] = (208, 245, 240)
FAR_FISH_COLOR: tuple[int, int, int] = (58, 120, 138)
KELP_COLOR: tuple[int, int, int] = (30, 96, 92)
KELP_COLOR_LIGHT: tuple[int, int, int] = (44, 128, 118)

WHALE_BODY: tuple[int, int, int] = (74, 130, 196)       # friendly blue
WHALE_BODY_LIGHT: tuple[int, int, int] = (108, 168, 226)
WHALE_OUTLINE: tuple[int, int, int] = (38, 78, 128)     # soft darker edge
WHALE_GLOW: tuple[int, int, int] = (150, 214, 246)      # gentle halo
WHALE_BELLY: tuple[int, int, int] = (232, 244, 252)
WHALE_CHEEK: tuple[int, int, int] = (246, 168, 176)
WHALE_EYE: tuple[int, int, int] = (34, 44, 58)
WHALE_SPOUT: tuple[int, int, int] = (236, 252, 255)

CORAL_COLORS: tuple[tuple[int, int, int], ...] = (
    (232, 120, 128),   # rosy coral
    (240, 158, 96),    # warm orange
    (214, 132, 196),   # soft magenta
    (128, 196, 168),   # sea green
)
CORAL_SHADOW: tuple[int, int, int] = (18, 52, 66)
SEAWEED_COLOR: tuple[int, int, int] = (46, 140, 110)
SEAWEED_COLOR_DARK: tuple[int, int, int] = (30, 104, 84)

BUBBLE_COLOR: tuple[int, int, int] = (226, 250, 255)
SPLASH_COLOR: tuple[int, int, int] = (236, 250, 255)

TEXT_COLOR: tuple[int, int, int] = (245, 253, 255)
TEXT_SHADOW: tuple[int, int, int] = (14, 44, 60)
TEXT_ACCENT: tuple[int, int, int] = (255, 214, 120)
PANEL_COLOR: tuple[int, int, int] = (16, 56, 78)
PANEL_BORDER: tuple[int, int, int] = (108, 200, 210)

# --------------------------------------------------------------------------- #
# UI / fonts
# --------------------------------------------------------------------------- #
FONT_NAME: str = "comicsansms,segoeui,arial"  # Rounded/friendly, with fallbacks.
FONT_SIZE_HUGE: int = 68
FONT_SIZE_LARGE: int = 44
FONT_SIZE_MEDIUM: int = 28
FONT_SIZE_SMALL: int = 20

# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #
HIGHSCORE_FILE: str = "highscore.json"
LEADERBOARD_FILE: str = "leaderboard.json"
LEADERBOARD_SIZE: int = 10          # How many top scores to keep.
INITIALS_LENGTH: int = 3            # Arcade-style 3-letter name entry.
DEFAULT_INITIALS: str = "AAA"       # Pre-filled entry / fallback name.

# --------------------------------------------------------------------------- #
# Game states
# --------------------------------------------------------------------------- #
STATE_TITLE: str = "title"
STATE_PLAYING: str = "playing"
STATE_GAMEOVER: str = "gameover"
STATE_LEADERBOARD: str = "leaderboard"
