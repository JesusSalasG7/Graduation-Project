"""
theme.py

Geometría de la interfaz, paleta de colores y duraciones de animación de
2048 -- constantes compartidas por los estados y los helpers de dibujo.
"""
from __future__ import annotations

import settings
from src.logic2048 import GRID_SIZE

# ---------------------------------------------------------------------------
# Geometría de la interfaz (superficie virtual, ver settings.py)
# ---------------------------------------------------------------------------
WINDOW_WIDTH = settings.WINDOW_WIDTH
WINDOW_HEIGHT = settings.WINDOW_HEIGHT

BOARD_LEFT = 30
BOARD_TOP = 150
CELL_SIZE = 140
CELL_GAP = 16
BOARD_PIXEL_SIZE = GRID_SIZE * CELL_SIZE + (GRID_SIZE + 1) * CELL_GAP  # 640

# ---------------------------------------------------------------------------
# Paleta de colores "neón espacial", extraída con muestreo de píxeles de
# referencia.jpeg (color picker programático sobre la imagen, no a ojo).
# ---------------------------------------------------------------------------
# Fondo: degradado diagonal azul marino -> púrpura, con resplandores en las
# esquinas y una tarjeta oscura con borde brillante conteniendo el juego.
COLOR_BACKGROUND_TOP = (13, 20, 48)       # esquina superior (azul marino)
COLOR_BACKGROUND_BOTTOM = (46, 12, 46)    # esquina inferior (púrpura oscuro)
COLOR_GLOW_BLUE = (60, 110, 230)          # halo esquina superior-izquierda
COLOR_GLOW_MAGENTA = (200, 40, 150)       # halo esquina inferior-derecha

COLOR_PANEL = (19, 23, 46)              # tarjeta central donde vive el juego
COLOR_PANEL_BORDER = (100, 140, 255)    # color base del resplandor del borde

COLOR_BOARD = (13, 16, 32)              # marco del tablero (más oscuro que las celdas)
COLOR_TEXT_PRIMARY = (240, 236, 227)    # texto principal: blanco cálido
COLOR_TEXT_MUTED = (135, 143, 173)      # texto secundario: gris azulado
COLOR_TITLE_GLOW = (245, 190, 90)       # resplandor dorado detrás del título

COLOR_TEXT_DARK = (55, 60, 72)      # texto de fichas 2 y 4 (fondos claros)
COLOR_TEXT_LIGHT = (250, 248, 244)  # texto de fichas >= 8 (fondos saturados)

COLOR_WIN = (255, 209, 102)   # dorado
COLOR_LOSE = (255, 107, 107)  # rojo/rosa neón

TILE_COLORS = {
    0: (44, 50, 68),      # celda vacía
    2: (196, 201, 204),   # gris plateado
    4: (219, 197, 160),   # beige/tostado
    8: (236, 135, 47),    # naranja
    16: (209, 95, 22),    # naranja quemado
    32: (246, 68, 54),    # rojo
    64: (177, 47, 195),   # púrpura
    128: (242, 200, 4),   # dorado
    256: (255, 221, 0),   # amarillo neón
    512: (0, 217, 219),   # cian
    1024: (6, 119, 213),  # azul
    2048: (233, 30, 140), # magenta neón
}
COLOR_TILE_EXTRA = (18, 0, 26)  # fichas > 2048, violeta casi negro

# Mapea el identificador de acción registrado en InputHandler (main.py) a
# la dirección que entiende Board.move().
#   1) "sliding":   las fichas existentes viajan de su celda de origen
#                   a su celda de destino (incluidas las que se
#                   fusionan, que convergen en la misma celda).
#   2) "appearing": el tablero ya muestra los valores finales; las
#                   celdas resultado de una fusión y la ficha nueva
#                   hacen un pequeño "pop" de escala para que se noten.
# Mientras cualquiera de las dos fases está activa se ignoran nuevas
# entradas de movimiento, para no encimar animaciones.
# ---------------------------------------------------------------------------
SLIDE_DURATION = 0.13
APPEAR_DURATION = 0.09
