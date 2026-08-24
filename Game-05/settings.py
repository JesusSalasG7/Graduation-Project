"""
Transmutacion Arcana

This file contains the game settings: input bindings, window/board
layout constants, fonts, and the tile spritesheet. Board tiles are cut
out of tiles.png (an 8x8 icon spritesheet) and scaled to TILE_SIZE, one
icon row per TileKind (src/board/tile.py) -- each row is one of the 8
combat elements. The board sits at the top of the screen; the combat
strip below it (player left, enemy right) is driven by src/combat/.
"""

from pathlib import Path

import pygame

from gale import input_handler

input_handler.InputHandler.set_keyboard_action(input_handler.KEY_ESCAPE, "quit")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_KP_ENTER, "enter")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_RETURN, "enter")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_UP, "up")
input_handler.InputHandler.set_keyboard_action(input_handler.KEY_DOWN, "down")
input_handler.InputHandler.set_mouse_click_action(input_handler.MOUSE_BUTTON_1, "click")

BASE_DIR = Path(__file__).parent

TITLE = "Transmutacion Arcana"

# --- Cover / splash --------------------------------------------------
COVER_IMAGE_PATH = BASE_DIR / "assets" / "graphics" / "ui" / "cover.jpg"

# --- Window ---------------------------------------------------------
# VIRTUAL is a lower internal resolution than WINDOW on purpose so the
# final upscale stays crisp. The aspect ratio is 512:624 (portrait) --
# the board sits on top and a combat strip for the two characters sits
# below it -- and WINDOW keeps that same ratio so gale's
# scale-to-window-size blit doesn't stretch it. VIRTUAL was doubled
# (from 256x312) to sharpen everything drawn at this resolution -- most
# noticeably the start-screen cover art (assets/graphics/ui/cover.jpg,
# a much higher-res photo) -- while WINDOW stayed the same physical
# size, so the final upscale shrank from x3 to x1.5 instead of growing
# the window itself.
VIRTUAL_WIDTH = 512
VIRTUAL_HEIGHT = 624

WINDOW_WIDTH = 768
WINDOW_HEIGHT = 936

# --- Board layout -----------------------------------------------------
BOARD_WIDTH = 6
BOARD_HEIGHT = 6
TILE_SIZE = 64

BOARD_PIXEL_WIDTH = BOARD_WIDTH * TILE_SIZE
BOARD_PIXEL_HEIGHT = BOARD_HEIGHT * TILE_SIZE

BOARD_X = (VIRTUAL_WIDTH - BOARD_PIXEL_WIDTH) // 2
BOARD_Y = 48

# --- Screen zones -------------------------------------------------------
TOP_BAR_ZONE = pygame.Rect(0, 0, VIRTUAL_WIDTH, BOARD_Y)
BOARD_ZONE = pygame.Rect(BOARD_X, BOARD_Y, BOARD_PIXEL_WIDTH, BOARD_PIXEL_HEIGHT)

# --- Combat strip -------------------------------------------------------
# Sits right below the board, full width, split in half: player on the
# left, enemy on the right. Anchors are each character sprite's center.
_COMBAT_ZONE_Y = BOARD_Y + BOARD_PIXEL_HEIGHT + 16
_COMBAT_ZONE_HEIGHT = VIRTUAL_HEIGHT - _COMBAT_ZONE_Y
PLAYER_PANEL = pygame.Rect(0, _COMBAT_ZONE_Y, VIRTUAL_WIDTH // 2, _COMBAT_ZONE_HEIGHT)
ENEMY_PANEL = pygame.Rect(
    VIRTUAL_WIDTH // 2, _COMBAT_ZONE_Y, VIRTUAL_WIDTH // 2, _COMBAT_ZONE_HEIGHT
)
PLAYER_ANCHOR = PLAYER_PANEL.center
ENEMY_ANCHOR = ENEMY_PANEL.center

# --- Combat balance -----------------------------------------------------
# El enemigo tiene mas vida que el jugador: no juega el tablero (ver
# CombatManager.enemy_turn), asi que su unica forma de ser un rival
# duro es aguantar mas turnos mientras su ataque escala (ver
# src.combat.combat_manager.ENEMY_RAMP_TURNS/ENEMY_ELEMENT_WEIGHTS).
PLAYER_MAX_HP = 100
ENEMY_MAX_HP = 115

# Limite de tiempo del combate, en segundos: si se agota antes de que
# el jugador derrote al enemigo, gana el enemigo (ver
# PlayState.update/COMBAT_TIME_LIMIT en src/states/play_state.py). Corre
# en tiempo real desde que arranca el combate, sin importar de quien
# sea el turno, para meter presion incluso mientras el jugador piensa
# la proxima jugada.
COMBAT_TIME_LIMIT = 50

CHARACTER_SPRITE_BASE_SIZE = 16  # pixel-art drawn on a 16x16 surface...
CHARACTER_SPRITE_SCALE = 6  # ...then blown up 6x with nearest-neighbor scaling.
CHARACTER_SPRITE_SIZE = CHARACTER_SPRITE_BASE_SIZE * CHARACTER_SPRITE_SCALE

HP_BAR_WIDTH = 128
HP_BAR_HEIGHT = 16
HP_BAR_OFFSET_Y = CHARACTER_SPRITE_SIZE // 2 + 28  # above the sprite's anchor

# --- Match-3 scoring -------------------------------------------------------
POINTS_PER_TILE = 10
CATALYSIS_BONUS = 50
# Desafio A05 (src/algorithm.py::find_repeated, aplicado en
# Board.resolve_runs): la Catalisis paga esto por cada elemento que
# se REPITE (aparece 2 o mas veces) dentro de la fila/columna que
# limpio, para premiar que un mismo elemento "resuene" varias veces
# en la misma linea, no solo el tamano del match.
RESONANCE_BONUS_PER_KIND = 15

# --- Tile kinds -------------------------------------------------------
# Matches src.board.tile.TileKind ordering: FUEGO, AGUA, TIERRA, AIRE,
# ELECTRICIDAD, HIELO, MAGIA, OSCURIDAD. tiles.png is an 8-column x
# 8-row icon sheet whose rows happen to already match that exact
# element order, so each TileKind is drawn from column 0 of the row
# with the same index.
TILES_IMAGE_PATH = BASE_DIR / "assets" / "graphics" / "board" / "tiles.png"
TILE_SHEET_COLUMNS = 8
TILE_SHEET_ROWS = 8
TILE_SPRITE_ROW = {i: i for i in range(TILE_SHEET_ROWS)}


def _content_bands(has_content: list) -> list:
    """
    Turn a list of per-pixel "is this row/column non-background" flags
    into a list of (start, end) ranges, one per contiguous run of
    content. Used to find each icon's real bounding box below.
    """
    bands = []
    start = None
    for i, flagged in enumerate(has_content):
        if flagged and start is None:
            start = i
        elif not flagged and start is not None:
            bands.append((start, i))
            start = None
    if start is not None:
        bands.append((start, len(has_content)))
    return bands


def _load_tile_sprites() -> dict:
    sheet = pygame.image.load(TILES_IMAGE_PATH)
    sheet_width, sheet_height = sheet.get_size()

    # The icons aren't laid out edge-to-edge in a clean 8x8 grid --
    # each one sits on an irregular pitch with padding baked into the
    # sheet (525 / 8 = 65.625 per cell, but icons are ~58px with ~5px
    # gaps and a ~13px outer border). Dividing the sheet size by the
    # grid count clips or bleeds neighboring icons into the crop, so
    # instead we detect each icon's real bounding box by scanning for
    # rows/columns that contain any non-background pixel.
    background = sheet.get_at((0, 0))
    col_has_content = [False] * sheet_width
    row_has_content = [False] * sheet_height
    for y in range(sheet_height):
        for x in range(sheet_width):
            if sheet.get_at((x, y)) != background:
                col_has_content[x] = True
                row_has_content[y] = True

    column_bands = _content_bands(col_has_content)
    row_bands = _content_bands(row_has_content)

    sprites = {}
    for kind, row in TILE_SPRITE_ROW.items():
        x0, x1 = column_bands[0]
        y0, y1 = row_bands[row]
        piece_rect = pygame.Rect(x0, y0, x1 - x0, y1 - y0)
        piece = sheet.subsurface(piece_rect).copy()
        sprites[kind] = pygame.transform.smoothscale(piece, (TILE_SIZE, TILE_SIZE))

    return sprites


TILE_SPRITES = _load_tile_sprites()

# --- Element sounds ---------------------------------------------------
# One cue per TileKind, played by CombatManager the moment a match of
# that element triggers its combat effect (src/combat/combat_manager.py).
# Keyed by the same plain ints as TILE_SPRITE_ROW/TileKind's values
# (FUEGO=0, AGUA=1, TIERRA=2, AIRE=3, ELECTRICIDAD=4, HIELO=5, MAGIA=6,
# OSCURIDAD=7) rather than importing TileKind, since src.board.tile
# already imports this module.
AUDIO_DIR = BASE_DIR / "assets" / "audio"
ELEMENT_SOUND_FILES = {
    0: AUDIO_DIR / "Fire.mp3",  # FUEGO
    1: AUDIO_DIR / "Water.mp3",  # AGUA
    2: AUDIO_DIR / "Earth.mp3",  # TIERRA
    3: AUDIO_DIR / "Air.mp3",  # AIRE
    4: AUDIO_DIR / "Electric.mp3",  # ELECTRICIDAD
    5: AUDIO_DIR / "Ice.mp3",  # HIELO
    6: AUDIO_DIR / "Magic.mp3",  # MAGIA
    7: AUDIO_DIR / "Darkness.mp3",  # OSCURIDAD
}


def _load_element_sounds() -> dict:
    pygame.mixer.init()
    return {kind: pygame.mixer.Sound(path) for kind, path in ELEMENT_SOUND_FILES.items()}


ELEMENT_SOUNDS = _load_element_sounds()

# --- Background music ---------------------------------------------------
# Un solo tema (Bucle_Music.mp3) suena de punta a punta del juego --
# arranca una vez desde TransmutacionArcana.init() (src/transmutacion_arcana.py)
# y sigue de fondo sin importar el estado (start/play) o cuantas
# partidas se reinicien. Se reproduce con pygame.mixer.music (pensado
# para streaming de un solo tema largo) en vez de mixer.Sound como
# ELEMENT_SOUNDS (pensado para efectos cortos que se disparan y
# superponen entre si) y a menor volumen que esos efectos -- que no
# fijan volumen propio, es decir quedan al maximo (1.0) -- para que no
# tape las senales de combate.
BACKGROUND_MUSIC_PATH = AUDIO_DIR / "Bucle_Music.mp3"
BACKGROUND_MUSIC_VOLUME = 0.4


def play_background_music() -> None:
    pygame.mixer.music.load(BACKGROUND_MUSIC_PATH)
    pygame.mixer.music.set_volume(BACKGROUND_MUSIC_VOLUME)
    pygame.mixer.music.play(loops=-1)


BACKGROUND_COLOR = (18, 14, 26)

FONTS = {
    "small": pygame.font.Font(None, 28),
    "medium": pygame.font.Font(None, 44),
    "large": pygame.font.Font(None, 80),
    "huge": pygame.font.Font(None, 112),
}
