"""
Window/gameplay configuration and asset loading for TypeBeat -- a typing
game with a Guitar-Hero-style "highway": 4 fixed vertical lanes carry
falling note-letters down towards a hit zone, and the player has to
press the matching key as each one crosses it.

Mirrors the layout of Game-01/settings.py: one module, imported once,
that owns every constant/sprite/font/sound the rest of the codebase
reads from -- no project code hardcodes a magic number that belongs
here.

Visual identity: minimalist dark-mode retro terminal -- solid near-black
background, a monospaced system font (no bitmap pixel-art asset), and a
small neon accent palette (gold for score/UI, blue/orange for notes)
instead of Game-01's arcade beveled look.
"""
import pathlib
from typing import List

import pygame

from gale import input_handler

pygame.font.init()
# Explicit format (not just pygame.mixer.init()'s defaults) because
# src/audio/sound_manager.py renders raw PCM at this exact sample rate/layout.
pygame.mixer.init(frequency=44100, size=-16, channels=2)

BASE_DIR = pathlib.Path(__file__).parent

# --- Window / virtual resolution --------------------------------------------
# Wider than Game-01's 480x360: falling letters need horizontal room to
# spread across the 4-lane highway.
VIRTUAL_WIDTH = 640
VIRTUAL_HEIGHT = 360

WINDOW_SCALE = 2.5
WINDOW_WIDTH = int(VIRTUAL_WIDTH * WINDOW_SCALE)
WINDOW_HEIGHT = int(VIRTUAL_HEIGHT * WINDOW_SCALE)

# --- Highway / lane layout --------------------------------------------------
# Falling notes travel in a straight vertical line from FALL_START_Y
# (just under the HUD) to HIT_ZONE_Y (where the player is meant to press
# the key) -- see Note.sync, which derives a note's y directly from
# World.elapsed every frame rather than accumulating its own dt.
FALL_START_Y = 80
HIT_ZONE_Y = 230
HIT_ZONE_HEIGHT = 3

TARGET_WORD_Y = 272

# The next QUEUE_PREVIEW_COUNT words waiting in World's lookahead (see
# World.upcoming_words), stacked one below another underneath the
# target word -- see TypingRenderer._render_word_queue.
QUEUE_START_Y = 296
QUEUE_LINE_HEIGHT = 15
QUEUE_PREVIEW_COUNT = 3

# 4 fixed vertical lanes (the "highway"), centered on the virtual canvas.
# A falling letter's lane is assigned by src/entities/lane_manager.py's
# LaneManager (see World._spawn_word), not derived from its position in
# the word -- see the lane-assignment block below for its tuning knobs.
LANE_COUNT = 4
LANE_SPACING = 108
NOTE_RADIUS = 14
HIT_TARGET_RADIUS = 17

# --- Non-sequential lane assignment (src/entities/lane_manager.py) --------
# Which hand each lane belongs to on a 4-key layout.
LEFT_HAND_LANES = (0, 1)
RIGHT_HAND_LANES = (2, 3)
# Sampling weight LaneManager gives the next lane, relative to whichever
# hand the CURRENT lane belongs to -- switching hands is weighted several
# times heavier than staying on it, which is what keeps play alternating
# between left/right instead of drifting into long same-hand runs.
LANE_SWITCH_HAND_WEIGHT = 3.0
LANE_SAME_HAND_WEIGHT = 1.0
# A 3rd repeat of the same lane in a row is rejected and resampled, and
# so is any candidate that would complete a straight LANE_COUNT-long
# staircase (0->1->2->3 or 3->2->1->0) -- see LaneManager._is_allowed.
LANE_MAX_SAME_LANE_STREAK = 2

# --- Timing / difficulty -------------------------------------------------
# travel_time: seconds a note spends falling from FALL_START_Y to
# HIT_ZONE_Y -- the main "how much reaction time do I get" knob.
DIFFICULTIES = {
    "facil": {"label": "Facil", "travel_time": 3.1},
    "normal": {"label": "Normal", "travel_time": 2.3},
    "dificil": {"label": "Dificil", "travel_time": 1.6},
}
DEFAULT_DIFFICULTY = "normal"

# --- Rhythm source: a real song's detected beat -----------------------------
# Letters land on this song's actual steady pulse (see
# src/audio/beat_detector.py and World._pick_next_beat_time) instead of
# purely an arbitrary fixed cadence -- travel_time above still sets the
# floor for how soon the *next* letter's beat is allowed to land, and
# (unlike an early version of this that let some beats skip ahead of it)
# always ends up exactly that far away, which is what gives every note
# the same constant fall speed -- see World._activate_letter.
AUDIO_DIR = BASE_DIR / "assets" / "audio"


def _discover_songs() -> List[pathlib.Path]:
    """
    Every .mp3 under AUDIO_DIR, sorted by filename -- PlayState's
    "A que ritmo quieres ir" song-select screen (shown before the
    controls screen) builds its menu straight off this list, so how many
    songs are actually available is deliberately NOT a fixed number:
    dropping a new .mp3 in that folder is the entire process for adding
    a choice, no separate registry to also keep in sync.
    """
    return sorted(AUDIO_DIR.glob("*.mp3"))


SONGS = _discover_songs()
assert SONGS, f"No .mp3 files found in {AUDIO_DIR} -- TypeBeat needs at least one song to run."

# The .stem (filename minus extension) doubles as the song's display
# title on that same menu -- one less thing to keep in sync per song.
SONG_TITLES = [path.stem for path in SONGS]
DEFAULT_SONG_INDEX = 0

SONG_VOLUME = 0.5  # mixed under the procedural miss SFX so that always reads clearly on top

BEAT_DETECTION_DELTA = 0.2  # kept for BeatDetector's cache key / API stability, see its docstring

# A hit_time landing squarely on a real beat only actually reads as
# "synced to the song" if a player watching can SEE it happen on every
# beat, not just on the sparse few a letter happens to land on -- see
# World.time_since_last_beat / TypingRenderer._render_hit_zone, which
# pulse the hit zone brighter/larger for this long right after each main
# beat. Comfortably under a beat interval at this song's own detected
# tempo (see librosa.beat.beat_track in beat_detector.py, which reads
# the tempo off the audio itself rather than a hardcoded BPM) so one
# pulse always fully settles before the next one starts.
BEAT_PULSE_DURATION_SECONDS = 0.12
BEAT_PULSE_RADIUS_BONUS = 6

# A gap this long (seconds) between two consecutive detected beats reads
# as a real musical pause rather than just this song's normal beat
# spacing -- see World._compute_pause_windows / highway_visibility. The
# highway fades out for the whole pause and back in over the last
# effective_travel_time seconds before the next block of notes resumes,
# so a quiet stretch never shows an empty highway sitting there for no
# visible reason -- see TypingRenderer._render_lanes / _render_hit_zone
# / _render_target_word.
SONG_PAUSE_GAP_SECONDS = 2.0

# How much the highway's ambient look rides the song's own macro loudness
# (see World.energy_at_elapsed) -- separate from, and slower/subtler
# than, the sharp per-beat pulse above: a quiet verse and the loudest
# drop should never look identical. Deliberately modest maximum -- the
# dark-terminal look has to survive even a sustained energy=1.0 stretch,
# not just read as a flash.
ENERGY_LANE_BRIGHTEN_MAX = 0.45  # lane separator lines, blended towards white

# Disco background: the fill color continuously crossfades around this
# yellow -> red -> blue -> yellow loop (real time, not beat-locked -- a
# steady rotation reads as "disco lights" better than a jump on every
# beat would) -- see TypingRenderer._disco_color. How far the background
# actually travels towards whichever color is current, at any moment,
# still rides World.energy_at_elapsed (0 at the quietest, this at the
# loudest) -- same "the picture should feel the song's dynamics, not
# just its beat" idea as ENERGY_LANE_BRIGHTEN_MAX above.
DISCO_COLORS = (
    pygame.Color(255, 214, 40),  # yellow
    pygame.Color(230, 45, 60),  # red
    pygame.Color(50, 110, 255),  # blue
)
DISCO_CYCLE_SECONDS_PER_COLOR = 4.0
DISCO_BACKGROUND_TINT_MAX = 0.24

# Gameplay rides the same curve, not just the lights: at energy=1.0 (the
# song's loudest passages) World.effective_travel_time is divided by this
# on top of speed_multiplier, so letters both fall faster AND arrive more
# often during a drop/chorus than during a quiet verse -- see
# World.effective_travel_time. 1.0 at energy=0.0 (no change at all in the
# quietest stretches).
ENERGY_SPEED_MULTIPLIER_MAX = 1.5

# As a run gets further into the song (its own duration, conceptually
# divided into 5 equal sections that each end a bit faster than the
# last -- see World._song_section_multiplier), effective_travel_time is
# divided by a smoothly, continuously climbing multiplier: 1.0 right at
# the start, this by the very end. A discrete per-section step was tried
# first and produced a real, visible jolt in fall speed the instant a
# section boundary passed -- exactly two consecutive letters suddenly
# falling at different speeds, which read as a bug rather than
# "progressively harder". Unlike speed_multiplier (streak-based, can
# only climb) and energy_at_elapsed (loudness-based, goes up AND down),
# this one is a plain, always-forward difficulty ramp tied purely to how
# much of the song has played -- every run gets harder purely by lasting
# longer, on top of whatever the other two are doing.
SONG_SECTION_SPEED_MULTIPLIER_MAX = 1.6

# --- Word generation (src/entities/word_stream.py) -----------------------
# Words alternate between these two length buckets so short/long variety
# is guaranteed rather than left to chance.
SHORT_WORD_LENGTH_RANGE = (3, 4)
LONG_WORD_LENGTH_RANGE = (7, 11)
MAX_WORD_GENERATION_ATTEMPTS = 40

# How many words World keeps generated-but-not-yet-active, ready to hand
# to _begin_word the instant the current one completes -- see
# World._ensure_lookahead. Exposed via World.upcoming_words; at least
# QUEUE_PREVIEW_COUNT so the queue stack always has that many real words
# to show instead of running dry.
WORD_LOOKAHEAD_COUNT = QUEUE_PREVIEW_COUNT

# --- Sorting exercise (src/algorithms/sort_task.py) -----------------------
# How many words get generated and handed to sort_words_by_length() every
# time a run starts (see PlayState._begin_sort_task) -- unrelated to
# WORD_LOOKAHEAD_COUNT above, this is a one-shot batch sorted before
# gameplay begins, not the actual falling-letter word supply.
SORT_TASK_WORD_COUNT = 500
# How long the loading/result screen stays up once sort_words_by_length()
# actually returns something -- purely cosmetic pacing (real quicksort
# over 500 words takes well under a millisecond), so the "N palabras
# ordenadas en X ms" readout is actually readable instead of flashing by
# in one frame.
SORT_LOADING_DISPLAY_SECONDS = 1.5

# The length-sorted preset batch above is still strictly ascending
# overall, but see src/algorithms/word_length_variety.py's
# group_in_ascending_blocks, an unrelated presentation filter PlayState
# runs it through afterward: this many words of one length before moving
# up to the next (3 of length 3, then 3 of length 4, then the next
# length that actually exists, looping back to the shortest for
# whatever's left) instead of every word of one length in a single
# uninterrupted block.
WORD_LENGTH_BLOCK_SIZE = 3

# --- Scoring / precision windows -----------------------------------------
# Distance (seconds) between the key press and the letter's ideal
# hit_time. Whichever window the distance falls in decides the
# judgement; a press further than the last (OK) window away is simply
# ignored (see World.handle_key) instead of counting as anything.
#
# OK_WINDOW_SECONDS doubles as World._expire_missed_letter's grace period
# -- an unpressed letter can't be declared a miss any sooner than the
# widest window a late press could still score in, so this is also
# exactly how long a letter sits parked at the hit zone, unresolved,
# before that auto-miss (and the life it costs) actually lands. These
# used to be looser (0.12 / 0.28 / 0.45) back when nothing on screen
# helped a player anticipate the exact instant to press -- now that the
# hit zone visibly pulses on every beat (see World.time_since_last_beat)
# and every note falls at one constant, predictable speed, that
# generosity just reads as an unresolved letter sitting there too long
# with no feedback, so these are tighter.
PERFECT_WINDOW_SECONDS = 0.10
GOOD_WINDOW_SECONDS = 0.20
OK_WINDOW_SECONDS = 0.28

JUDGEMENT_POINTS = {
    "perfect": 100,
    "good": 60,
    "ok": 25,
    "miss": 0,
}
JUDGEMENT_LABELS = {
    "perfect": "PERFECTO",
    "good": "BIEN",
    "ok": "OK",
    "miss": "FALLO",
}

# Weighted contribution of each judgement towards World.accuracy_percent
# -- a Bien/Ok hit still counts as mostly-accurate rather than being
# averaged in as a flat miss, the same way real rhythm games score
# accuracy independently of raw point totals.
ACCURACY_WEIGHTS = {
    "perfect": 1.0,
    "good": 0.8,
    "ok": 0.5,
    "miss": 0.0,
}

# Every COMBO_MULTIPLIER_STEP_SIZE consecutive non-miss hits raises the
# score multiplier by COMBO_MULTIPLIER_STEP, capped at
# COMBO_MULTIPLIER_MAX -- the "the better your streak, the more it's
# worth" feel Guitar Hero-style games are built around.
COMBO_MULTIPLIER_STEP_SIZE = 10
COMBO_MULTIPLIER_STEP = 0.25
COMBO_MULTIPLIER_MAX = 2.0

# Awarded once per word, on top of its letters' own points, if every
# letter in it resolved as anything but a miss.
WORD_CLEAN_BONUS = 50

STARTING_LIVES = 4

# --- Progressive speed ----------------------------------------------------
# World.speed_multiplier starts at 1.0 and climbs every SPEED_COMBO_STEP_SIZE
# CONSECUTIVE non-miss hits (a miss resets the streak, not the multiplier
# already earned -- see World._maybe_increase_speed), capped at
# SPEED_MULTIPLIER_MAX. It divides the active difficulty's travel_time (see
# World.effective_travel_time), so a higher multiplier both shortens how
# long each letter takes to fall AND how soon the next one's hit_time
# lands -- fall rate and spawn cadence speed up together.
SPEED_MULTIPLIER_START = 1.0
SPEED_COMBO_STEP_SIZE = 10
SPEED_INCREMENT_PER_COMBO_STEP = 0.02
SPEED_MULTIPLIER_MAX = 2.5

# How long a resolved note (hit or miss) keeps flashing its judgement
# color at the hit zone before it's dropped -- purely cosmetic feedback,
# World doesn't know this constant exists.
LETTER_RESOLVED_FLASH_SECONDS = 0.18

# How long a judgement popup ("PERFECTO", "FALLO"...) stays on screen
# before fading out.
JUDGEMENT_POPUP_SECONDS = 0.6

# How long the giant translucent combo number stays fully visible in the
# middle of the highway before fading -- only shown once a combo is
# actually going (see TypingRenderer._render_combo_watermark).
COMBO_WATERMARK_MIN_COMBO = 2

# --- Palette: minimalist dark-mode retro terminal ---------------------------
BACKGROUND_COLOR = pygame.Color(15, 15, 15)
LANE_SEPARATOR_COLOR = pygame.Color(45, 45, 45)
HIT_ZONE_COLOR = pygame.Color(255, 200, 40)  # gold

NEON_GOLD = pygame.Color(255, 200, 40)
NEON_BLUE = pygame.Color(0, 200, 255)
NEON_ORANGE = pygame.Color(255, 120, 30)
TERMINAL_GREEN = pygame.Color(80, 255, 130)
TERMINAL_RED = pygame.Color(255, 70, 70)

# Alternates by lane index (see src/rendering/typing_renderer.py::letter_lane)
# -- just the two accent colors the brief calls for, one per lane parity.
LANE_COLORS = (NEON_BLUE, NEON_ORANGE, NEON_BLUE, NEON_ORANGE)

UI_TEXT_COLOR = pygame.Color(225, 225, 225)
UI_ACCENT_COLOR = NEON_GOLD
UI_MUTED_COLOR = pygame.Color(110, 110, 110)

JUDGEMENT_COLORS = {
    "perfect": TERMINAL_GREEN,
    "good": NEON_BLUE,
    "ok": NEON_ORANGE,
    "miss": TERMINAL_RED,
}

TARGET_SLOT_PENDING_COLOR = pygame.Color(75, 75, 75)  # not the current letter yet
TARGET_SLOT_CURRENT_COLOR = pygame.Color(255, 255, 255)  # bright white -- next to type
TARGET_SLOT_DONE_COLOR = TERMINAL_GREEN
TARGET_SLOT_MISSED_COLOR = TERMINAL_RED
QUEUE_TEXT_COLOR = pygame.Color(85, 85, 85)  # dim gray for the upcoming-letters stack

HEART_FULL_COLOR = TERMINAL_RED
HEART_EMPTY_COLOR = pygame.Color(55, 40, 40)

COMBO_WATERMARK_COLOR = NEON_GOLD
COMBO_WATERMARK_ALPHA = 55  # semi-transparent, sits behind everything else


def _build_heart_sprite(filled: bool) -> pygame.Surface:
    """
    Small pixel-art heart for the lives HUD, native-res drawn then
    nearest-neighbor scaled, matching the technique Game-01 uses for its
    apple/trophy sprites (see Game-01/settings.py::_build_apple_sprite).
    Kept as the one deliberately "drawn" sprite in an otherwise flat/text
    UI -- a heart reads faster at a glance than a number would here.
    """
    native_size = 10
    pixels = pygame.Surface((native_size, native_size), pygame.SRCALPHA)
    color = HEART_FULL_COLOR if filled else HEART_EMPTY_COLOR

    cx1, cy1 = 3.0, 3.2
    cx2, cy2 = 6.5, 3.2
    lobe_radius = 2.6

    for y in range(native_size):
        for x in range(native_size):
            in_left_lobe = ((x - cx1) ** 2 + (y - cy1) ** 2) <= lobe_radius**2
            in_right_lobe = ((x - cx2) ** 2 + (y - cy2) ** 2) <= lobe_radius**2
            # Rough triangular point beneath the two lobes.
            in_point = y >= 5 and abs(x - 4.75) <= (9.5 - y) * 0.85

            if in_left_lobe or in_right_lobe or in_point:
                pixels.set_at((x, y), color)

    return pygame.transform.scale(pixels, (round(native_size * 1.5), round(native_size * 1.5)))


SPRITES = {
    "heart_full": _build_heart_sprite(True),
    "heart_empty": _build_heart_sprite(False),
}

# --- Fonts ---------------------------------------------------------------
# System monospace, not a bundled bitmap font -- pygame.font.SysFont
# tries each name in order and falls back to pygame's own default
# monospace if none of these are installed, so the terminal look still
# holds up on a machine without Consolas/Courier New.
FONT_FAMILY = "consolas,couriernew,dejavusansmono,monospace"

FONTS = {
    "hud": pygame.font.SysFont(FONT_FAMILY, 12),
    "note": pygame.font.SysFont(FONT_FAMILY, 13, bold=True),
    "letter": pygame.font.SysFont(FONT_FAMILY, 18, bold=True),
    "queue": pygame.font.SysFont(FONT_FAMILY, 10),
    "menu": pygame.font.SysFont(FONT_FAMILY, 15),
    "title": pygame.font.SysFont(FONT_FAMILY, 28, bold=True),
    "popup": pygame.font.SysFont(FONT_FAMILY, 13, bold=True),
    "combo_watermark": pygame.font.SysFont(FONT_FAMILY, 64, bold=True),
}

# --- Input -------------------------------------------------------------
# Same binding vocabulary Game-01 established: "restart" for ENTER
# (confirm/dismiss, reused everywhere), "text_char"/"text_backspace" for
# raw character entry. Here "text_char" also doubles as gameplay input --
# PlayState reads input_data.unicode either as a letter to drop into the
# lane system or as a record-name character, depending on which UI mode
# it's currently in (same pattern PlayState in Game-01 uses to
# disambiguate direction keys between movement and menu navigation).
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_ESCAPE, "quit")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_UP, "move_up")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_DOWN, "move_down")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_RETURN, "restart")

for _char in "abcdefghijklmnopqrstuvwxyz0123456789":
    input_handler.InputHandler.set_keyboard_action(
        getattr(input_handler, f"KEY_{_char}"), "text_char"
    )
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_SPACE, "text_char")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_BACKSPACE, "text_backspace")
