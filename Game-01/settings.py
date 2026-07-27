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
MOVE_INTERVAL = 0.12

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


_map_texture = pygame.image.load(IMAGES_DIR / "map.jpg")

SPRITES = {
    "map": pygame.transform.smoothscale(_map_texture, (VIRTUAL_WIDTH, VIRTUAL_HEIGHT)),
    "apple": _build_apple_sprite(),
}

FONTS = {
    "hud": pygame.font.SysFont("Arial", 14),
    "title": pygame.font.SysFont("Arial", 28, bold=True),
}

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
# per match to the defaults below). The actual accept/reject decision is
# intentionally left unimplemented -- see World._apple_passes_filter and
# World._handle_challenge_apple_eaten.
CHALLENGE_APPLE_VALUES = (-5, 5, 15)
CHALLENGE_APPLE_VALUE_COLORS = {
    -5: pygame.Color(198, 40, 40),   # toxic red
    5: pygame.Color(56, 142, 60),    # safe green
    15: pygame.Color(255, 179, 0),   # premium gold
}
CHALLENGE_FILTER_MIN_DEFAULT = 0
CHALLENGE_FILTER_MAX_DEFAULT = 10

# An apple that lands outside the active filter range doesn't sit there
# forever: it gets a random countdown (seconds) drawn from this range and,
# once it expires, is replaced by a freshly rolled apple -- see
# World._spawn_apple / World._update_apple_timers.
CHALLENGE_OUT_OF_RANGE_LIFETIME_RANGE = (3.0, 6.0)

input_handler.InputHandler.set_keyboard_action(input_handler.KEY_ESCAPE, "quit")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_UP, "move_up")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_DOWN, "move_down")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_LEFT, "move_left")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_RIGHT, "move_right")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_RETURN, "restart")
