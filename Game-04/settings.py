"""
Window, input, font, color, and sound configuration for the Mirror Code
game. Every setting gale.game.Game understands (window/virtual
resolution, FPS, ...) falls back to whatever is defined here -- see
gale.conf.global_settings for the full list.
"""
import pathlib

import pygame

from gale import input_handler

# No need to call pygame.mixer.init() here: importing anything under
# gale (input_handler above, for instance) already calls pygame.init(),
# which initializes every subsystem pygame ships with, mixer included.

BASE_DIR = pathlib.Path(__file__).parent
ASSETS_DIR = BASE_DIR / "assets"
SOUNDS_DIR = ASSETS_DIR / "sounds"

TITLE = "Espejo de Códigos"

VIRTUAL_WIDTH = 480
VIRTUAL_HEIGHT = 270

WINDOW_SCALE = 2.5
WINDOW_WIDTH = round(VIRTUAL_WIDTH * WINDOW_SCALE)
WINDOW_HEIGHT = round(VIRTUAL_HEIGHT * WINDOW_SCALE)

FPS = 60

# Default pygame font (no external .ttf files needed) at a handful of
# sizes, one per role -- see src/states/play_state.py and
# src/states/results_state.py for where each is used.
#
# Each entry is (family, size in virtual pixels, bold): family None means
# pygame's default font. Kept as specs (not just Font objects) so
# src/text.py can rebuild the same font at window resolution and draw
# text crisply instead of upscaling it from the 480x270 canvas.
FONT_SPECS = {
    "title": (None, 18, False),
    "prompt": (None, 20, False),
    "transmission": (None, 26, False),
    "button": (None, 18, False),
    "feedback": (None, 16, False),
    "hint": (None, 14, False),
    "results_title": (None, 20, False),
    "stats": (None, 16, False),
    # Monospace, terminal-styled text for StoryState -- pygame.font.SysFont
    # always returns a usable font, falling back to the default one if none
    # of the requested families is installed, so this never needs an asset
    # file of its own.
    "console": ("consolas,couriernew,monospace", 13, False),
    # Monospace too, so the digits don't jitter the layout sideways as the
    # per-round countdown changes every frame -- see PlayState.render.
    "timer": ("consolas,couriernew,monospace", 24, True),
    "game_over_title": (None, 34, False),
}


def load_font(family, size: int, bold: bool) -> pygame.font.Font:
    font = pygame.font.Font(None, size) if family is None else pygame.font.SysFont(family, size)
    font.set_bold(bold)
    return font


FONTS = {key: load_font(*spec) for key, spec in FONT_SPECS.items()}

# Dark, high-contrast, sci-fi palette shared by every screen.
COLORS = {
    "background": pygame.Color(6, 10, 20),
    "panel_background": pygame.Color(13, 19, 34),
    "border": pygame.Color(0, 210, 225),
    "text": pygame.Color(222, 236, 245),
    "text_dim": pygame.Color(140, 160, 180),
    "accent": pygame.Color(0, 225, 255),
    "button_background": pygame.Color(17, 27, 46),
    "button_hover": pygame.Color(27, 45, 72),
    "button_border": pygame.Color(0, 210, 225),
    "success": pygame.Color(70, 230, 140),
    "error": pygame.Color(255, 90, 100),
    "warning": pygame.Color(255, 185, 60),
    # StoryState's terminal look.
    "console_background": pygame.Color(0, 0, 0),
    "console_text": pygame.Color(80, 230, 120),
    # Explosion particle palette, warm colors from white-hot core to ember.
    "explosion_core": pygame.Color(255, 245, 210),
}

# "intro" loops while StoryState's letters are typing themselves out
# (see StoryState.enter/exit); "explosion" plays once when a round's
# countdown reaches zero (see GameOverState.enter); "clock" loops while
# a round's countdown is actively running; "correct"/"incorrect" play
# once each time a round is answered, matching the green/red feedback
# text (see PlayState._handle_answer); "victory" plays once when all
# TOTAL_ROUNDS are completed in time (see ResultsState.enter).
SOUNDS = {
    "intro": pygame.mixer.Sound(SOUNDS_DIR / "Computer_Sound.mp3"),
    "explosion": pygame.mixer.Sound(SOUNDS_DIR / "Boom.mp3"),
    "clock": pygame.mixer.Sound(SOUNDS_DIR / "Clock.mp3"),
    "correct": pygame.mixer.Sound(SOUNDS_DIR / "Correct.mp3"),
    "incorrect": pygame.mixer.Sound(SOUNDS_DIR / "Incorrect.mp3"),
    "victory": pygame.mixer.Sound(SOUNDS_DIR / "Congratulations.mp3"),
}

input_handler.InputHandler.set_keyboard_action(input_handler.KEY_ESCAPE, "quit")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_r, "restart")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_RETURN, "confirm")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_SPACE, "confirm")
input_handler.InputHandler.set_mouse_click_action(input_handler.MOUSE_BUTTON_1, "mouse_click")
input_handler.InputHandler.set_mouse_motion_action(None, "mouse_motion")
