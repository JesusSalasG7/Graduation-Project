"""
instructions.py

Panel "Cómo jugar" que PlayState dibuja sobre el tablero al empezar la
partida (y cuando el jugador presiona H): objetivo, cómo se mueven y se
fusionan las fichas, cuándo aparece una ficha nueva, cómo se gana y se
pierde, un ejemplo dibujado de un movimiento y los controles.
"""
from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

import pygame

from src.rendering.theme import (
    COLOR_PANEL,
    COLOR_PANEL_BORDER,
    COLOR_TEXT_DARK,
    COLOR_TEXT_LIGHT,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    COLOR_TITLE_GLOW,
    TILE_COLORS,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)

CARD_MARGIN_X = 36
CARD_TOP = 34
CARD_BOTTOM_MARGIN = 34
PADDING = 26
LINE_GAP = 3
SECTION_GAP = 8

EXAMPLE_TILE = 44
EXAMPLE_GAP = 6

# (título, texto) de cada sección, en orden.
SECTIONS: Sequence[Tuple[str, str]] = (
    ("Objetivo", "Combina fichas con el mismo número hasta formar una ficha con el 2048."),
    ("Mover", "Usa las flechas del teclado. TODAS las fichas se deslizan juntas hacia ese "
              "lado hasta chocar con el borde o con otra ficha."),
    ("Fusionar", "Si dos fichas con el mismo número chocan, se unen en una sola con la suma "
                 "(2+2=4, 4+4=8, ...). Cada ficha se fusiona una sola vez por movimiento."),
    ("Ficha nueva", "Después de cada movimiento aparece un 2 (a veces un 4) en una casilla vacía."),
    ("Puntuación", "Cada fusión suma a tu puntuación el valor de la ficha que se forma."),
    ("Fin de la partida", "Ganas al formar el 2048. Pierdes si el tablero se llena y ya no "
                          "queda ninguna fusión posible."),
)

EXAMPLE_BEFORE = (2, 2, 4, 0)
EXAMPLE_AFTER = (4, 4, 0, 0)

_fonts: Dict[str, pygame.font.Font] = {}


def _font(name: str) -> pygame.font.Font:
    if not _fonts:
        _fonts["title"] = pygame.font.SysFont("arial", 38, bold=True)
        _fonts["heading"] = pygame.font.SysFont("arial", 21, bold=True)
        _fonts["body"] = pygame.font.SysFont("arial", 18)
        _fonts["tile"] = pygame.font.SysFont("arial", 22, bold=True)
        _fonts["footer"] = pygame.font.SysFont("arial", 22, bold=True)
    return _fonts[name]


def _wrap(text: str, font: pygame.font.Font, max_width: int) -> List[str]:
    lines: List[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and font.size(candidate)[0] > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _draw_example_row(surface: pygame.Surface, values: Tuple[int, ...], left: int, top: int) -> int:
    """Dibuja una fila de 4 fichas de ejemplo; devuelve el borde derecho."""
    x = left
    for value in values:
        rect = pygame.Rect(x, top, EXAMPLE_TILE, EXAMPLE_TILE)
        pygame.draw.rect(surface, TILE_COLORS.get(value, TILE_COLORS[0]), rect, border_radius=5)
        if value:
            color = COLOR_TEXT_DARK if value <= 4 else COLOR_TEXT_LIGHT
            text = _font("tile").render(str(value), True, color)
            surface.blit(text, text.get_rect(center=rect.center))
        x += EXAMPLE_TILE + EXAMPLE_GAP
    return x - EXAMPLE_GAP


def draw_instructions(surface: pygame.Surface) -> None:
    # Velo oscuro sobre el tablero y tarjeta centrada con el texto.
    veil = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
    veil.fill((5, 7, 18, 200))
    surface.blit(veil, (0, 0))

    card = pygame.Rect(
        CARD_MARGIN_X, CARD_TOP, WINDOW_WIDTH - 2 * CARD_MARGIN_X,
        WINDOW_HEIGHT - CARD_TOP - CARD_BOTTOM_MARGIN,
    )
    pygame.draw.rect(surface, COLOR_PANEL, card, border_radius=20)
    pygame.draw.rect(surface, COLOR_PANEL_BORDER, card, width=2, border_radius=20)

    left = card.left + PADDING
    max_width = card.width - 2 * PADDING

    title = _font("title").render("CÓMO JUGAR", True, COLOR_TITLE_GLOW)
    surface.blit(title, title.get_rect(midtop=(card.centerx, card.top + 18)))
    y = card.top + 18 + title.get_height() + 14

    body = _font("body")
    for heading, text in SECTIONS:
        surface.blit(_font("heading").render(heading, True, COLOR_TITLE_GLOW), (left, y))
        y += _font("heading").get_height() + LINE_GAP
        for line in _wrap(text, body, max_width):
            surface.blit(body.render(line, True, COLOR_TEXT_PRIMARY), (left, y))
            y += body.get_height() + LINE_GAP
        y += SECTION_GAP - LINE_GAP

    # Ejemplo: [2][2][4][ ]  --flecha izquierda-->  [4][4][ ][ ]
    surface.blit(_font("heading").render("Ejemplo", True, COLOR_TITLE_GLOW), (left, y))
    y += _font("heading").get_height() + 6
    row_right = _draw_example_row(surface, EXAMPLE_BEFORE, left, y)
    # Flecha dibujada (no un carácter: la fuente del sistema puede no
    # tener el glifo) con la tecla que se presionó encima.
    arrow_left, arrow_right = row_right + 16, row_right + 136
    arrow_y = y + EXAMPLE_TILE // 2 + 8
    label = body.render("presionas IZQ.", True, COLOR_TEXT_MUTED)
    surface.blit(label, label.get_rect(midbottom=((arrow_left + arrow_right) // 2, arrow_y - 4)))
    pygame.draw.line(surface, COLOR_TEXT_MUTED, (arrow_left, arrow_y), (arrow_right - 8, arrow_y), 3)
    pygame.draw.polygon(
        surface, COLOR_TEXT_MUTED,
        [(arrow_right, arrow_y), (arrow_right - 12, arrow_y - 7), (arrow_right - 12, arrow_y + 7)],
    )
    _draw_example_row(surface, EXAMPLE_AFTER, arrow_right + 16, y)
    y += EXAMPLE_TILE + 6
    for line in _wrap(
        "Los dos 2 se unen en un 4 y el 4 que ya estaba se desliza a su lado: "
        "no se une con el 4 nuevo en el mismo movimiento.",
        body, max_width,
    ):
        surface.blit(body.render(line, True, COLOR_TEXT_MUTED), (left, y))
        y += body.get_height() + LINE_GAP

    controls = body.render(
        "Flechas: mover   R: reiniciar   H: instrucciones   ESC: salir", True, COLOR_TEXT_MUTED
    )
    surface.blit(controls, controls.get_rect(midbottom=(card.centerx, card.bottom - 50)))

    footer = _font("footer").render("Presiona ENTER o una flecha para empezar", True, COLOR_TEXT_PRIMARY)
    surface.blit(footer, footer.get_rect(midbottom=(card.centerx, card.bottom - 18)))
