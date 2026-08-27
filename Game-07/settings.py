"""
Window/gameplay configuration for the procedural-maze slider prototype:
a "Tomb of the Mask" style grid slider whose level is generated at
runtime by a cellular automaton (see src/world/level_generator.py).

Mirrors the layout other Game-XX/settings.py modules use: one module,
imported once, owning every constant the rest of the codebase reads
from -- no project code hardcodes a magic number that belongs here.
"""
import pygame

from gale import input_handler

pygame.font.init()

TITLE = "Procedural Maze Slider"

# --- Grid / virtual resolution -------------------------------------------
# 40x30 cells at 16px each keeps the automaton's corridors chunky enough
# to read clearly on screen while still giving it room to grow real mazes.
GRID_COLUMNS = 40
GRID_ROWS = 30
CELL_SIZE = 16

VIRTUAL_WIDTH = GRID_COLUMNS * CELL_SIZE
VIRTUAL_HEIGHT = GRID_ROWS * CELL_SIZE

WINDOW_SCALE = 1.5
WINDOW_WIDTH = int(VIRTUAL_WIDTH * WINDOW_SCALE)
WINDOW_HEIGHT = int(VIRTUAL_HEIGHT * WINDOW_SCALE)

FPS = 60

# --- Cellular automaton (src/world/level_generator.py) -------------------
# "Maze" rule (B3/S12345). Counter-intuitively this needs initial noise
# close to 50/50, not the sparse handful-of-percent a cave-generation
# automaton (B4678/S35678 and similar) uses: at low density almost every
# seed wall starts out isolated (0 wall neighbors), and the survive rule
# can't save a cell with 0 neighbors (survive_min is at best 1), so
# nearly the entire seed dies on iteration 1 and nothing is left to grow
# corridors from. A dense 50/50 seed instead already has wall clusters
# everywhere, and B3/S12345 sculpts those into a static network of
# winding 1-cell corridors within a handful of iterations (it settles
# into a still life, so extra iterations past that point are free
# insurance, not wasted work).
CA_WALL_PROBABILITY = 0.5
CA_ITERATIONS = 10
CA_BIRTH_LIMIT = 3
CA_SURVIVE_MIN = 1
CA_SURVIVE_MAX = 5

# Regeneration safety net (src/world/level.py): re-rolls a handful of
# times so every level clears two bars -- a decently sized open area, and
# a spawn-to-goal path that's actually long enough to be worth solving --
# rather than capping how the CA is normally allowed to turn out.
CA_MIN_OPEN_CELLS = 200
CA_MIN_GOAL_DISTANCE = 25  # in cells, via BFS shortest path
CA_MAX_GENERATION_ATTEMPTS = 15

# --- Goal & obstacles (src/world/level.py) --------------------------------
# The goal is placed at the cell with the longest shortest-path distance
# from spawn (a BFS eccentricity search), not a random open cell -- that
# guarantees reaching it actually means solving the maze rather than
# possibly spawning right next to it.
#
# Obstacles are scattered at random over the remaining open cells and are
# hazards, not walls: they don't block a slide, but entering one sends
# the player back to spawn (see Player.warp_to). None are placed within
# OBSTACLE_SAFE_RADIUS (BFS steps) of spawn, so the player always gets a
# few guaranteed-safe cells to react in before the first hazard can
# appear.
OBSTACLE_DENSITY = 0.012  # fraction of the open region turned into hazards
OBSTACLE_SAFE_RADIUS = 3

# --- Player (src/entities/player.py) --------------------------------------
# Cells per second while sliding -- fast enough that a slide reads as
# "shot down the corridor", not a walk.
PLAYER_SPEED_CELLS_PER_SECOND = 14.0

# --- Palette ---------------------------------------------------------------
BACKGROUND_COLOR = pygame.Color(20, 20, 28)
WALL_COLOR = pygame.Color(70, 70, 90)
PLAYER_COLOR = pygame.Color(240, 200, 60)
GOAL_COLOR = pygame.Color(80, 230, 120)
OBSTACLE_COLOR = pygame.Color(230, 70, 70)
HUD_TEXT_COLOR = pygame.Color(225, 225, 225)
WIN_BANNER_COLOR = pygame.Color(80, 230, 120)

# --- Fonts -------------------------------------------------------------
FONT_FAMILY = "consolas,couriernew,dejavusansmono,monospace"
FONTS = {
    "hud": pygame.font.SysFont(FONT_FAMILY, 12),
    "banner": pygame.font.SysFont(FONT_FAMILY, 22, bold=True),
}

# --- Input ------------------------------------------------------------------
# Arrows and WASD both drive the same 4 movement actions; PlayState is the
# one that decides whether a given press actually starts a slide (see
# Player.try_move -- ignored entirely while already moving).
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_ESCAPE, "quit")

input_handler.InputHandler.set_keyboard_action(input_handler.KEY_UP, "move_up")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_w, "move_up")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_DOWN, "move_down")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_s, "move_down")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_LEFT, "move_left")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_a, "move_left")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_RIGHT, "move_right")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_d, "move_right")

# Re-rolls a brand new level on the spot -- lets a run of the prototype
# show off several outputs of the automaton without restarting the app.
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_r, "regenerate")
