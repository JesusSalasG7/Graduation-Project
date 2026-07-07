import pathlib

import pygame

from gale import frames
from gale import input_handler
from typing import Dict
from gale.frames import generate_frames
from src import loaders

input_handler.InputHandler.set_keyboard_action(input_handler.KEY_ESCAPE, "quit")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_p, "pause")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_RETURN, "enter")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_KP_ENTER, "enter")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_RIGHT, "move_right")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_d, "move_right")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_LEFT, "move_left")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_a, "move_left")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_SPACE, "jump")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_x, "attack")
input_handler.InputHandler.set_mouse_click_action(input_handler.MOUSE_BUTTON_1, "attack")

BOARD_WIDTH = 2
BOARD_HEIGHT = 2

TILE_SIZE = 75

# Size we want to emulate
VIRTUAL_WIDTH = 400
VIRTUAL_HEIGHT = 192

BOARD_OFFSET_X = VIRTUAL_WIDTH / 2 - (TILE_SIZE*2)/2
BOARD_OFFSET_Y = VIRTUAL_HEIGHT / 2 - (TILE_SIZE*2)/2


# Size of our actual window
WINDOW_WIDTH = VIRTUAL_WIDTH * 4
WINDOW_HEIGHT = VIRTUAL_HEIGHT * 4

PLAYER_SPEED = 80

BOSS_SPEED = 60

GRAVITY = 900

NUM_LEVELS = 2

TILEMAP: Dict[str, Dict[int, str] ]= {

    "level1": {

        #TEXTURAS
        (1,176):"tiles",
        (177,248):"creatures",
        (249,376):"tiles2",
        (376,379):"creatures2",
    },
    "level2": {
        #TEXTURAS
        (1,60):"tiles3",
        (61,72): "creatures3",
        (73,144): "creatures",
        (145,320) :"tiles",
        (321,333): "creatures2",
    }
}

BASE_DIR = pathlib.Path(__file__).parent

LevelLoader = loaders.TmxLevelLoader

TEXTURES = {
    "tiles": pygame.image.load(BASE_DIR / "assets" / "textures" / "tileset.png"),
    "puzzle": pygame.image.load(BASE_DIR / "assets" / "textures" / "imagen.jpg"),
    "tiles2": pygame.image.load(BASE_DIR / "assets" / "textures" / "tileset2.png"),
    "tiles3": pygame.image.load(BASE_DIR / "assets" / "textures" / "tileset3.png"),
    "Knight_Walk": pygame.image.load(BASE_DIR / "assets" / "textures" / "Knight_Walk.png"),
    "Knight_Walk2": pygame.image.load(BASE_DIR / "assets" / "textures" / "Knight_Walk2.png"),
    "Knight_Attack": pygame.image.load(BASE_DIR / "assets" / "textures" / "Knight_Attack.png"),
    "Knight_Attack2": pygame.image.load(BASE_DIR / "assets" / "textures" / "Knight_Attack2.png"),
    "dead_Walk": pygame.image.load(BASE_DIR / "assets" / "textures" / "dead_Walk.png"),
    "dead_Attack": pygame.image.load(BASE_DIR / "assets" / "textures" / "dead_Attack.png"),
    "creatures": pygame.image.load(BASE_DIR / "assets" / "textures" / "creatures.png"),
    "creatures2": pygame.image.load(BASE_DIR / "assets" / "textures" / "creatures2.png"),
    "creatures3": pygame.image.load(BASE_DIR / "assets" / "textures" / "creatures3.png"),
    "hearts": pygame.image.load(BASE_DIR / "assets" / "textures" / "hearts.png"),
    "shot": pygame.image.load(BASE_DIR / "assets" / "textures" / "shot.png"),
    "Begin": pygame.image.load(BASE_DIR / "assets" / "textures" / "Begin.png"),
    "End": pygame.image.load(BASE_DIR / "assets" / "textures" / "End.png"),
    "background": pygame.image.load(BASE_DIR / "assets" / "textures" / "background.png"),
    "dead": pygame.image.load(BASE_DIR / "assets" / "textures" / "dead.png"),
    "live_boss": pygame.image.load(BASE_DIR / "assets" / "textures" / "live_boss.png"),
    "Puzzle": pygame.image.load( BASE_DIR / "assets" / "textures" / "Puzzle.jpg"),
    "key": pygame.image.load(BASE_DIR / "assets" / "textures" / "key.png"),
    "boss_gate": pygame.image.load(BASE_DIR / "assets" / "textures" / "boss_gate.png"),
}

FRAMES = {
    "tiles": frames.generate_frames(TEXTURES["tiles"], 16, 16),
    "tiles2": frames.generate_frames(TEXTURES["tiles2"], 16, 16),
    "tiles3": frames.generate_frames(TEXTURES["tiles3"], 16, 16),
    "Knight_Walk": frames.generate_frames(TEXTURES["Knight_Walk"], 16, 17),
    "Knight_Walk2": frames.generate_frames(TEXTURES["Knight_Walk2"], 16, 17),
    "Knight_Attack": frames.generate_frames(TEXTURES["Knight_Attack"], 25, 17),
    "Knight_Attack2": frames.generate_frames(TEXTURES["Knight_Attack2"], 25, 17),
    "dead_Walk": frames.generate_frames(TEXTURES["dead_Walk"], 38, 59),
    "dead_Attack": frames.generate_frames(TEXTURES["dead_Attack"], 48, 56),
    "creatures": frames.generate_frames(TEXTURES["creatures"], 16, 16),
    "creatures2": frames.generate_frames(TEXTURES["creatures2"], 16, 16),
    "creatures3": frames.generate_frames(TEXTURES["creatures3"], 16, 18),
    "hearts": frames.generate_frames(TEXTURES["hearts"], 10, 9),
    "shot": frames.generate_frames(TEXTURES["shot"],16,16 ),
    "puzzle": frames.generate_frames(TEXTURES["puzzle"], TILE_SIZE, TILE_SIZE),
    "dead": frames.generate_frames(TEXTURES["dead"], 32, 23),
    "live_boss": frames.generate_frames(TEXTURES["live_boss"], 24, 9),
    "Puzzle": generate_frames(TEXTURES["Puzzle"], TILE_SIZE, TILE_SIZE),
    "key": frames.generate_frames(TEXTURES["key"], 16, 16),
    "boss_gate": frames.generate_frames(TEXTURES["boss_gate"], 16, 64),
}

TILEMAPS = {
    i: BASE_DIR / "assets" / "tilemaps" / f"level{i}" for i in range(1, NUM_LEVELS + 1)
}

pygame.mixer.init()

SOUNDS = {
    "pickup_coin": pygame.mixer.Sound(BASE_DIR / "assets" / "sounds" / "pickup_coin.wav"),
    "jump": pygame.mixer.Sound(BASE_DIR / "assets" / "sounds" / "SFX_Jump_33.mp3"),
    "attack": pygame.mixer.Sound(BASE_DIR / "assets" / "sounds" / "attack.mp3"),
    "dead": pygame.mixer.Sound(BASE_DIR / "assets" / "sounds" / "dead.wav"),
    "gameover": pygame.mixer.Sound(BASE_DIR / "assets" / "sounds" / "gameover.mp3"),
    "wounded": pygame.mixer.Sound(BASE_DIR / "assets" / "sounds" / "wounded.wav"),
    "count": pygame.mixer.Sound(BASE_DIR / "assets" / "sounds" / "count.wav"),
    "win_level": pygame.mixer.Sound(BASE_DIR / "assets" / "sounds" / "Win_level.ogg"),
    "begin": pygame.mixer.Sound(BASE_DIR / "assets" / "sounds" / "music_begin.wav")
}


SOUNDS["pickup_coin"].set_volume(0.5)


pygame.font.init()

FONTS = {
    "small": pygame.font.Font(BASE_DIR / "assets" / "fonts" / "font.ttf", 7),
    "medium": pygame.font.Font(BASE_DIR / "assets" / "fonts" / "font.ttf", 16),
}