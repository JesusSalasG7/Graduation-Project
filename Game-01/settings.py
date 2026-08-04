"""
Window/grid configuration and asset loading for the Snake game.
"""
import pathlib

import pygame

from gale import input_handler

pygame.font.init()
# Explicit format (not just pygame.mixer.init()'s defaults) because
# src/audio/synth.py renders raw PCM at this exact sample rate/layout.
pygame.mixer.init(frequency=44100, size=-16, channels=2)
# Channels 0-1 are reserved for the ambient bed (see AMBIENT_CHANNEL_*
# below) so pygame.mixer.Sound.play()'s automatic channel picking for
# one-shot SFX -- crash/eat/move -- can never steal or cut it off.
pygame.mixer.set_reserved(2)

BASE_DIR = pathlib.Path(__file__).parent
ASSETS_DIR = BASE_DIR / "assets"
IMAGES_DIR = ASSETS_DIR / "images"
SOUNDS_DIR = ASSETS_DIR / "sounds"

# Grid / virtual resolution
CELL_SIZE = 24
GRID_COLS = 20
GRID_ROWS = 15

VIRTUAL_WIDTH = CELL_SIZE * GRID_COLS
VIRTUAL_HEIGHT = CELL_SIZE * GRID_ROWS

# Actual window size
WINDOW_SCALE = 2
WINDOW_WIDTH = VIRTUAL_WIDTH * WINDOW_SCALE
WINDOW_HEIGHT = VIRTUAL_HEIGHT * WINDOW_SCALE

# Seconds between grid steps: how often the snake advances one cell.
MOVE_INTERVAL = 0.15

# Classic green snake palette. The body alternates between the two
# greens per segment to read as scales; the head, eyes and tongue are
# drawn procedurally in WorldRenderer instead of loaded from art files.
SNAKE_COLORS = {
    "body_light": pygame.Color(102, 204, 92),
    "body_dark": pygame.Color(76, 175, 80),
    "outline": pygame.Color(27, 94, 32),
    "head": pygame.Color(56, 142, 60),
    "eye_white": pygame.Color("white"),
    "eye_pupil": pygame.Color(20, 20, 20),
    "tongue": pygame.Color(200, 30, 30),
    "mouth": pygame.Color(110, 20, 20),
}

# How close (in grid cells) the head has to get to an apple before the
# snake opens its mouth at it.
APPLE_PROXIMITY_RANGE = 3

# The tongue flicks on its own cycle, unrelated to the mouth: a short
# flick, then a random 1-2s pause before the next one.
TONGUE_FLICK_DURATION = 0.35
TONGUE_FLICK_PAUSE_RANGE = (1.0, 2.0)

# "Seeing stars" burst drawn where the snake hits a wall/itself: a
# handful of little stars circling the impact point.
STAR_COLOR = pygame.Color(255, 221, 51)
STAR_OUTLINE = pygame.Color(184, 134, 11)
STAR_COUNT = 3
STAR_ORBIT_RADIUS = CELL_SIZE * 1.4
STAR_ORBIT_SPEED = 3.5  # radians/second
STAR_SIZE = CELL_SIZE * 0.4
STAR_SPIN_SPEED = 6.0  # radians/second

# On impact the head recoils away from the hit, then eases back into
# its resting spot -- a single bounce, not a loop. Only the segments
# within BOUNCE_AFFECTED_SEGMENTS of the head join in, fading out with
# distance, so it reads as the front of the snake flinching rather
# than the whole body sliding as a rigid block.
BOUNCE_DURATION = 0.4
BOUNCE_DISTANCE = CELL_SIZE * 0.45
BOUNCE_AFFECTED_SEGMENTS = 3

def _build_apple_sprite() -> pygame.Surface:
    """
    Draws the apple as pixel art at a tiny native resolution, then
    scales it up with nearest-neighbor (not smoothscale) so the blocky
    pixels stay crisp instead of blurring into a smooth image.
    """
    native_size = 12
    pixels = pygame.Surface((native_size, native_size), pygame.SRCALPHA)

    red = (198, 40, 40, 255)
    red_dark = (123, 20, 20, 255)
    highlight = (255, 158, 140, 255)
    stem = (93, 64, 55, 255)
    leaf = (104, 189, 90, 255)

    center_x, center_y = 5.5, 6.5
    radius_x, radius_y = 4.6, 4.2

    for y in range(native_size):
        for x in range(native_size):
            nx = (x - center_x) / radius_x
            ny = (y - center_y) / radius_y
            dist = nx * nx + ny * ny

            if dist <= 1.0:
                pixels.set_at((x, y), red_dark if dist > 0.82 else red)

    # Dimple where the stem meets the body.
    pixels.set_at((5, 3), red_dark)
    pixels.set_at((6, 3), red_dark)

    # Shine highlight, upper-left of the body.
    for hx, hy in ((3, 5), (4, 5), (3, 6)):
        pixels.set_at((hx, hy), highlight)

    # Stem.
    pixels.set_at((6, 1), stem)
    pixels.set_at((6, 2), stem)

    # Leaf.
    for lx, ly in ((7, 0), (8, 0), (7, 1), (8, 1)):
        pixels.set_at((lx, ly), leaf)

    return pygame.transform.scale(pixels, (CELL_SIZE, CELL_SIZE))


def _build_trophy_sprite() -> pygame.Surface:
    """
    Draws the best-record trophy as pixel art at a tiny native resolution,
    then scales it up with nearest-neighbor (not smoothscale), same as
    _build_apple_sprite, so it reads as crisp blocky pixels in the HUD.
    """
    native_size = 14
    pixels = pygame.Surface((native_size, native_size), pygame.SRCALPHA)

    gold = (255, 193, 7, 255)
    gold_dark = (196, 130, 15, 255)
    highlight = (255, 235, 160, 255)
    outline = (110, 74, 15, 255)

    cup_center_x, cup_center_y = 6.5, 4.5
    cup_radius_x, cup_radius_y = 4.5, 3.5

    for y in range(native_size):
        for x in range(native_size):
            nx = (x - cup_center_x) / cup_radius_x
            ny = (y - cup_center_y) / cup_radius_y
            dist = nx * nx + ny * ny

            if dist <= 1.0:
                pixels.set_at((x, y), gold_dark if dist > 0.78 else gold)

    # Shine highlight, upper-left of the cup.
    for hx, hy in ((4, 2), (5, 2), (4, 3)):
        pixels.set_at((hx, hy), highlight)

    # Handles: small loops poking out either side of the cup.
    for hx, hy in ((0, 3), (1, 3), (0, 4), (0, 5), (1, 5)):
        pixels.set_at((hx, hy), outline)
    for hx, hy in ((13, 3), (12, 3), (13, 4), (13, 5), (12, 5)):
        pixels.set_at((hx, hy), outline)

    # Neck connecting the cup to the base.
    for y in (8, 9):
        for x in (6, 7):
            pixels.set_at((x, y), gold_dark)

    # Base plinth.
    for x in range(4, 10):
        pixels.set_at((x, 10), gold)
    for x in range(3, 11):
        pixels.set_at((x, 11), gold_dark)
    for x in range(2, 12):
        pixels.set_at((x, 12), outline)

    return pygame.transform.scale(pixels, (native_size * 2, native_size * 2))


# Native resolution/scale for the arrow-key sprites below, used by the
# controls modal (see src/rendering/controls_modal.py).
CONTROLS_SPRITE_NATIVE_SIZE = 12
CONTROLS_SPRITE_SCALE = 3


def _build_key_sprite(direction: str) -> pygame.Surface:
    """
    One arrow-keycap for the "how to play" modal: a keyboard key
    silhouette with a triangular arrow glyph pointing `direction`
    ("up"/"down"/"left"/"right"), drawn at native resolution and
    scaled up with nearest-neighbor, same technique as
    _build_apple_sprite/_build_trophy_sprite.
    """
    native_size = CONTROLS_SPRITE_NATIVE_SIZE
    pixels = pygame.Surface((native_size, native_size), pygame.SRCALPHA)

    face = (222, 226, 230, 255)
    shade = (176, 182, 190, 255)
    border = (60, 64, 70, 255)
    glyph = (40, 44, 50, 255)

    pygame.draw.rect(pixels, border, (0, 0, native_size, native_size), border_radius=2)
    pygame.draw.rect(pixels, face, (1, 1, native_size - 2, native_size - 2), border_radius=2)
    pygame.draw.line(pixels, shade, (1, native_size - 2), (native_size - 2, native_size - 2))

    center_x, center_y = native_size / 2, native_size / 2
    reach = 3.2

    tip = {
        "up": (center_x, center_y - reach),
        "down": (center_x, center_y + reach),
        "left": (center_x - reach, center_y),
        "right": (center_x + reach, center_y),
    }[direction]
    # Unit vector perpendicular to the arrow's direction, used to spread
    # the two base corners of the triangle out from the tip.
    perp = (1, 0) if direction in ("up", "down") else (0, 1)
    base_center = (center_x - (tip[0] - center_x) * 0.6, center_y - (tip[1] - center_y) * 0.6)
    base_a = (base_center[0] + perp[0] * 2.4, base_center[1] + perp[1] * 2.4)
    base_b = (base_center[0] - perp[0] * 2.4, base_center[1] - perp[1] * 2.4)

    pygame.draw.polygon(pixels, glyph, [tip, base_a, base_b])

    return pygame.transform.scale(
        pixels, (native_size * CONTROLS_SPRITE_SCALE, native_size * CONTROLS_SPRITE_SCALE)
    )


_map_texture = pygame.image.load(IMAGES_DIR / "map.jpg")

SPRITES = {
    "map": pygame.transform.smoothscale(_map_texture, (VIRTUAL_WIDTH, VIRTUAL_HEIGHT)),
    "apple": _build_apple_sprite(),
    "trophy": _build_trophy_sprite(),
    "key_up": _build_key_sprite("up"),
    "key_down": _build_key_sprite("down"),
    "key_left": _build_key_sprite("left"),
    "key_right": _build_key_sprite("right"),
}

FONTS = {
    "hud": pygame.font.SysFont("Arial", 14),
    "title": pygame.font.SysFont("Arial", 28, bold=True),
}

# White/yellow text (the previous choice) barely stands out against the
# board's lighter green tile -- these two read clearly against both
# tiles instead. Shared by MenuState and ControlsModal: UI_TEXT_COLOR
# for regular labels, UI_ACCENT_COLOR for whichever one is selected.
# UI_ACCENT_COLOR is a dark red rather than a bright one -- pure red
# washes out on the lighter tile just like the old yellow did.
UI_TEXT_COLOR = pygame.Color(20, 20, 20)
UI_ACCENT_COLOR = pygame.Color(139, 0, 0)

# Action SFX sit at full volume; the ambient bed below is deliberately
# mixed under this (see AMBIENT_BASE_VOLUME) so it never competes with
# them for headroom.
SFX_VOLUME = 1.0

SOUNDS = {
    "crash": pygame.mixer.Sound(SOUNDS_DIR / "Crash.mp3"),
    "eat": pygame.mixer.Sound(SOUNDS_DIR / "Eat.mp3"),
    "move": pygame.mixer.Sound(SOUNDS_DIR / "Move.mp3"),
}

for _sound in SOUNDS.values():
    _sound.set_volume(SFX_VOLUME)

# --- Main theme music -------------------------------------------------------
# Sound.mp3 is the atmosphere's main theme: one track, streamed through
# pygame.mixer.music (not a Sound/Channel like the SFX/ambient above) so
# an arbitrary-length mp3 doesn't have to be held fully in memory. Mixed
# 10 dB under SFX_VOLUME so it always sits behind the crash/eat/move cues.
THEME_MUSIC_PATH = SOUNDS_DIR / "Sound.mp3"
THEME_MUSIC_VOLUME_DB = -10.0
THEME_MUSIC_VOLUME = SFX_VOLUME * 10 ** (THEME_MUSIC_VOLUME_DB / 20)

# --- Ambient sound design --------------------------------------------------
# A soft synth-pad drone plays underneath gameplay: a few sine/triangle
# oscillators forming a chord, low-pass filtered to stay low/low-mid,
# rendered as a mathematically exact loop (no crossfade or edit needed
# to hide a seam -- see src/audio/synth.py). src/audio/ambient.py reads
# game state and picks which pre-rendered variant should be playing.

AMBIENT_LOOP_SECONDS = 4.0

# Discrete tempo/pitch steps the drone can sit at, from calmest (0) to
# most tense (AMBIENT_TENSION_LEVELS - 1). Driven by how much the snake
# has grown (and would also react to a future speed ramp -- see
# AmbientController.sync_with_world).
AMBIENT_TENSION_LEVELS = 4

# Snake length (in segments) at which tension tops out. Deliberately a
# fixed length rather than a fraction of the grid: tension is about
# "there's a lot of snake to steer now", which is independent of board
# size -- AMBIENT_SPACE_CRITICAL_RATIO below is what reacts to the
# board itself being full.
AMBIENT_GROWTH_TENSION_REFERENCE = 30
AMBIENT_ROOT_HZ = 130.81  # C3: low enough to stay out of the SFX's way
AMBIENT_CHORD_INTERVALS_SEMITONES = (0, 7, 12)  # root, fifth, octave
AMBIENT_CHORD_AMPLITUDES = (1.0, 0.55, 0.35)
AMBIENT_CHORD_WAVEFORMS = ("sine", "triangle", "sine")
AMBIENT_TENSION_SEMITONE_STEP = 2  # pitch rise per tension level
AMBIENT_TREMOLO_DEPTH = 0.22  # how deep the tempo pulse dips the volume

# Low-pass cutoff: keeps the ambience out of the mid-high band so the
# (brighter, more transient) crash/eat SFX always read clearly on top.
AMBIENT_LOWPASS_HZ = 900.0
AMBIENT_LOWPASS_CRITICAL_HZ = 480.0  # extra-muffled once space is tight

AMBIENT_BASE_VOLUME = 0.22  # stays well under SFX_VOLUME
AMBIENT_CRITICAL_VOLUME_SCALE = 0.75  # extra duck once space is critical
AMBIENT_DUCK_VOLUME_SCALE = 0.55  # brief dip so an eat/crash accent cuts through
AMBIENT_DUCK_SECONDS = 0.18

AMBIENT_CROSSFADE_SECONDS = 1.2

# Fraction of the grid that must still be free before the board reads
# as "critical" (packed), as opposed to merely "the snake has grown".
AMBIENT_SPACE_CRITICAL_RATIO = 0.15

AMBIENT_CHANNEL_A = 0
AMBIENT_CHANNEL_B = 1

# --- Challenge mode: "Filtro Metabolico de Valores" -------------------------
# Only used when World is built with mode="challenge" (see MenuState). Every
# apple gets a random numeric value from CHALLENGE_APPLE_VALUES; the snake
# can only safely eat values inside [filter_min, filter_max] (World, reset
# per match to the defaults below, then reshuffled periodically -- see
# World._update_filter_window). Accept/reject is World._apple_passes_filter
# / World._handle_challenge_apple_eaten.
CHALLENGE_APPLE_VALUES = (-5, 5, 15)
CHALLENGE_APPLE_VALUE_COLORS = {
    -5: pygame.Color(198, 40, 40),   # toxic red
    5: pygame.Color(56, 142, 60),    # safe green
    15: pygame.Color(255, 179, 0),   # premium gold
}

# Candidate [min, max] windows the active filter rotates through. Each one
# deliberately admits a different subset of CHALLENGE_APPLE_VALUES, so "how
# many apples on the board are in range right now" -- the answer
# World.count_apples_in_range() computes -- actually changes over a match
# instead of always landing on the same count.
CHALLENGE_FILTER_WINDOWS = (
    (0, 10),    # only +5
    (-5, 5),    # -5 and +5
    (5, 15),    # +5 and +15
    (-5, 15),   # all three
    (10, 20),   # only +15
)
CHALLENGE_FILTER_MIN_DEFAULT, CHALLENGE_FILTER_MAX_DEFAULT = CHALLENGE_FILTER_WINDOWS[0]
CHALLENGE_FILTER_RESHUFFLE_SECONDS = 8.0

# How many apples challenge mode keeps on the board at once -- this (not
# just a single apple) is the array World.count_apples_in_range() counts
# over. Classic mode is unaffected and keeps exactly one.
CHALLENGE_APPLE_COUNT = 6

# An apple that lands outside the active filter range doesn't sit there
# forever: it gets a random countdown (seconds) drawn from this range and,
# once it expires, is replaced by a freshly rolled apple -- see
# World._spawn_apple / World._update_apple_timers.
CHALLENGE_OUT_OF_RANGE_LIFETIME_RANGE = (3.0, 6.0)

# Every CHALLENGE_RANGE_BONUS_INTERVAL_SECONDS, World scores
# count_apples_in_range(): each apple currently sitting inside the active
# filter window is worth this many bonus points, on top of whatever eating
# it directly is worth -- see World._update_range_bonus.
CHALLENGE_RANGE_BONUS_INTERVAL_SECONDS = 5.0
CHALLENGE_RANGE_BONUS_PER_APPLE = 2

input_handler.InputHandler.set_keyboard_action(input_handler.KEY_ESCAPE, "quit")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_UP, "move_up")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_DOWN, "move_down")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_LEFT, "move_left")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_RIGHT, "move_right")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_RETURN, "restart")

# Raw character keys for the new-record name entry prompt (see PlayState).
# Bound to shared "text_char"/"text_backspace" actions instead of one
# binding per letter mattering individually -- the handler reads the
# actual character off KeyboardData.unicode.
for _char in "abcdefghijklmnopqrstuvwxyz0123456789":
    input_handler.InputHandler.set_keyboard_action(
        getattr(input_handler, f"KEY_{_char}"), "text_char"
    )
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_SPACE, "text_char")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_BACKSPACE, "text_backspace")
