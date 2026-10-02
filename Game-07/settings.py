"""
Window/gameplay configuration for Conway's Puzzle: a puzzle game built
on Conway's Game of Life (rule B3/S23). One module, imported once,
owning every constant the rest of the codebase reads from -- no project
code hardcodes a magic number that belongs here.
"""
import pathlib

import pygame

from gale import input_handler

pygame.font.init()

BASE_DIR = pathlib.Path(__file__).resolve().parent

TITLE = "Conway's Puzzle"

# --- Grid / virtual resolution -------------------------------------------
# Every level shares this canvas size (src/levels.py only varies what's
# drawn *inside* it -- walls, target zone, enemies, budget), so the
# renderer never has to deal with a level-dependent surface size.
GRID_COLUMNS = 26
GRID_ROWS = 15
CELL_SIZE = 24

HUD_HEIGHT = 40

VIRTUAL_WIDTH = GRID_COLUMNS * CELL_SIZE
VIRTUAL_HEIGHT = HUD_HEIGHT + GRID_ROWS * CELL_SIZE


def _window_scale() -> float:
    """
    Largest scale at which the window still fits the desktop (with room
    for the taskbar/title bar), never below the old fixed 1.5. The text
    is drawn at window resolution (src/text.py), so a bigger window means
    sharper letters; and when the launcher forces FULLSCREEN | SCALED,
    a window close to the monitor size keeps SDL's final upscale small.
    """
    try:
        pygame.display.init()
        desktop_width, desktop_height = pygame.display.get_desktop_sizes()[0]
    except (pygame.error, IndexError):
        return 1.5
    fit = min(desktop_width * 0.95 / VIRTUAL_WIDTH, desktop_height * 0.85 / VIRTUAL_HEIGHT)
    return max(1.5, fit)


WINDOW_SCALE = _window_scale()
WINDOW_WIDTH = int(VIRTUAL_WIDTH * WINDOW_SCALE)
WINDOW_HEIGHT = int(VIRTUAL_HEIGHT * WINDOW_SCALE)

FPS = 60

# --- Simulation -------------------------------------------------------------
# Seconds between automatic generations while the simulation is running
# (SPACE). Manual stepping (S) is not throttled by this.
GENERATION_INTERVAL = 0.12

# --- Palette ---------------------------------------------------------------
BACKGROUND_COLOR = pygame.Color(18, 18, 26)
HUD_BACKGROUND_COLOR = pygame.Color(12, 12, 18)
GRID_LINE_COLOR = pygame.Color(40, 40, 54)
WALL_COLOR = pygame.Color(70, 70, 90)
TARGET_ZONE_COLOR = pygame.Color(40, 90, 90)
TARGET_ZONE_ALIVE_COLOR = pygame.Color(90, 220, 210)
PLAYER_CELL_COLOR = pygame.Color(80, 230, 120)
ENEMY_CELL_COLOR = pygame.Color(230, 70, 70)
CURSOR_COLOR = pygame.Color(255, 255, 255)
HUD_TEXT_COLOR = pygame.Color(225, 225, 225)
HUD_ACCENT_COLOR = pygame.Color(240, 200, 60)
WIN_BANNER_COLOR = pygame.Color(80, 230, 120)
OVERLAY_BACKDROP_COLOR = pygame.Color(0, 0, 0)
ACHIEVEMENT_TOAST_COLOR = pygame.Color(240, 200, 60)
MENU_HIGHLIGHT_COLOR = pygame.Color(240, 200, 60)

# --- Achievements ------------------------------------------------------------
ACHIEVEMENT_TOAST_DURATION = 3.0  # seconds a toast stays on screen
ACHIEVEMENT_EFFICIENCY_THRESHOLD = 0.5  # win using at most 50% of the budget
ACHIEVEMENT_CHAIN_REACTION_BIRTHS = 8  # births in a single generation

# --- Audio -------------------------------------------------------------
# Background music is a stream (played through pygame.mixer.music, which
# only ever holds one track at a time), so it's referenced by path and
# loaded/played by whoever starts it -- unlike SOUNDS below, there's
# nothing to preload here.
BACKGROUND_MUSIC_PATH = str(BASE_DIR / "assets" / "sounds" / "background_music.mp3")

SOUNDS = {
    "click": pygame.mixer.Sound(str(BASE_DIR / "assets" / "sounds" / "Click_button.mp3")),
}

# --- Fonts -------------------------------------------------------------
FONT_FAMILY = "consolas,couriernew,dejavusansmono,monospace"
# (size on the virtual canvas, bold). FONTS holds them at virtual size
# (used for measuring/wrapping text); src/text.py rebuilds each one at
# window resolution when actually drawing, so letters stay sharp.
FONT_SPECS = {
    "hud": (13, False),
    "title": (28, True),
    "menu": (16, False),
    "banner": (22, True),
    "toast": (12, True),
}
FONTS = {
    key: pygame.font.SysFont(FONT_FAMILY, size, bold=bold)
    for key, (size, bold) in FONT_SPECS.items()
}

# --- Input --------------------------------------------------------------
# Action ids are intentionally generic (not tied to a single state):
# "confirm" selects a level in StartState, restarts it in PlayState, and
# advances to the next one in VictoryState; "back" backs out of whatever
# is currently on screen. "open_guide" (G) opens/closes the how-to-play
# guide from the level menu or mid-level.
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_ESCAPE, "back")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_RETURN, "confirm")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_KP_ENTER, "confirm")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_UP, "nav_up")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_DOWN, "nav_down")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_LEFT, "nav_left")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_RIGHT, "nav_right")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_g, "open_guide")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_i, "level_info")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_SPACE, "toggle_pause")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_s, "step_once")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_r, "clear_cells")

input_handler.InputHandler.set_mouse_click_action(
    input_handler.MOUSE_BUTTON_1, "place_cell"
)
input_handler.InputHandler.set_mouse_motion_action(None, "mouse_move")
