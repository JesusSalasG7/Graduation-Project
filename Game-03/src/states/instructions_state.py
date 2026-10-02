"""
Instructions screen, two pages: the first explains every control and
button currently in the game (see PlayState) -- camera, layer moves, and
the icon buttons (Shuffle/Auto/Eye/Search/Undo/Redo); the second
explains the 2x2x2 block search (challenge A03): what the target block
is, what the Search button does, and why it's worth looking at.
Reachable from MenuState's "Instructions" button; "Back" returns to it.

Row text is drawn through src/text.py (at window resolution, so it
stays readable once the tiny 480x270 canvas is upscaled); only the
pixel-art title and button labels are drawn on the canvas.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import pygame

from gale.conf import settings
from gale.input_handler import InputData, MouseClickData, MouseMotionData
from gale.state import BaseState

from src import text

COLOR_BG = pygame.Color(24, 26, 33)
COLOR_HEADING = pygame.Color(255, 213, 0)
COLOR_TEXT = pygame.Color(225, 225, 230)

LEFT_MARGIN = 14
TOP_MARGIN = 6
LINE_HEIGHT = 13
HEADER_EXTRA_GAP = 3  # extra breathing room above every header but the first
INDENT = 9
ROW_ICON_SIZE = 11
ROW_ICON_GAP = 3
ROW_ICON_COLOR = (225, 225, 230)

TITLE_SCALE = 2
BUTTON_TEXT_SCALE = 1.5

BACK_BUTTON_WIDTH = 112
BACK_BUTTON_HEIGHT = 22
BACK_BUTTON_BOTTOM_MARGIN = 8
PAGE_BUTTON_WIDTH = 100  # minimum; grows to fit its label
PAGE_BUTTON_GAP = 8

BUTTON_COLOR = pygame.Color(255, 255, 255)
BUTTON_HOVER_COLOR = pygame.Color(210, 225, 250)
BUTTON_BORDER_COLOR = pygame.Color(170, 170, 178)
BUTTON_TEXT_COLOR = (18, 18, 22)


@dataclass
class _Row:
    kind: str  # "header" or "line" (lines longer than the screen wrap)
    text: str
    icons: Tuple[str, ...] = field(default_factory=tuple)  # keys into settings.TEXTURES


# The actual list of controls/buttons this file documents -- keep in
# sync with src/states/play_state.py whenever a control changes there.
_ROWS: Tuple[_Row, ...] = (
    _Row("header", "CÁMARA"),
    _Row("line", "Arrastrar el mouse, o las flechas: rotar la cámara"),
    _Row("header", "MOVIMIENTOS"),
    _Row("line", "U D L R F B: girar esa cara (sentido horario)"),
    _Row("line", "+ Shift: sentido antihorario"),
    _Row("line", "+ Alt: capa doble   |   + Alt + Shift: capa doble antihoraria"),
    _Row("line", "M E S: capas del medio (+ Shift: antihorario)"),
    _Row("header", "BOTONES"),
    _Row("line", "Aplica 20 movimientos al azar, animados", icons=("shuffle",)),
    _Row("line", "Mezcla y activa el temporizador (abajo a la derecha)", icons=("auto",)),
    _Row("line", "Guía: marca qué cara es U/D/L/R/F/B", icons=("eye_open",)),
    _Row("line", "Busca un bloque 2x2x2 conocido (desafío A03)", icons=("search",)),
    _Row("line", "Deshacer / rehacer el último movimiento", icons=("undo", "redo")),
    _Row("header", "OTROS"),
    _Row("line", "Esc: salir del juego"),
)

# Second page: the idea behind the 2x2x2 search (challenge A03) -- keep
# in sync with PlayState's SEARCH_BLOCK_ORIGIN / _search_for_block.
_SEARCH_ROWS: Tuple[_Row, ...] = (
    _Row("header", "¿QUÉ ES EL BLOQUE OBJETIVO?"),
    _Row("line", "Al empezar, el juego guarda una esquina del cubo resuelto: un bloque de "
                 "2x2x2 = 8 piezas (la esquina naranja-amarilla-azul, caras L, D y B)."),
    _Row("header", "¿QUÉ HACE BUSCAR?", icons=("search",)),
    _Row("line", "Recorre las 8 posiciones donde cabe un bloque 2x2x2 dentro del cubo 3x3x3 "
                 "(una por cada esquina) y en cada una compara las piezas una por una; "
                 "apenas una no coincide, pasa a la siguiente posición."),
    _Row("line", "En amarillo: la posición que está revisando. En verde: dónde lo encontró."),
    _Row("header", "¿PARA QUÉ SIRVE?"),
    _Row("line", "Con el cubo resuelto, el bloque está en la posición (0, 0, 0). Al mezclar, "
                 "esas 8 piezas se separan y ya no se encuentra; si vuelves a armar esa "
                 "esquina, se encuentra de nuevo."),
    _Row("line", "Es reconocer un patrón 3D dentro de otro más grande. Armar primero un bloque "
                 "2x2x2 es el primer paso de métodos reales para resolver el cubo (Petrus)."),
)

_PAGES: Tuple[Tuple[str, Tuple[_Row, ...]], ...] = (
    ("INSTRUCCIONES", _ROWS),
    ("BUSCAR 2x2x2", _SEARCH_ROWS),
)


def _wrap(message: str, font_key: str, max_width: float) -> List[str]:
    lines: List[str] = []
    current = ""
    for word in message.split():
        candidate = f"{current} {word}".strip()
        if current and text.text_size(candidate, font_key)[0] > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


class InstructionsState(BaseState):
    def enter(self, *args: Tuple[Any], **kwargs: Dict[str, Any]) -> None:
        self._last_mouse_pos: Optional[Tuple[float, float]] = None

        self._body_font = settings.FONTS["body"]
        self._heading_font = settings.FONTS["body_bold"]

        self._page = 0
        self._title_surfaces = [
            text.pixel_label(title, (255, 255, 255), TITLE_SCALE)
            for title, _rows in _PAGES
        ]

        # Every button icon (shuffle.png, eye_open.png, ...) is a solid
        # black shape on a transparent background -- fine on the light
        # buttons in PlayState, but nearly invisible on this screen's
        # dark background. BLEND_RGBA_ADD adds RGB (with alpha 0, so it
        # doesn't touch the alpha channel) on top of the icon's own
        # black pixels, recoloring the shape to `ROW_ICON_COLOR` while
        # keeping its original antialiased silhouette intact.
        self._row_icons: Dict[str, pygame.Surface] = {}
        for row in _ROWS + _SEARCH_ROWS:
            for key in row.icons:
                if key in self._row_icons:
                    continue
                icon = pygame.transform.smoothscale(
                    settings.TEXTURES[key].convert_alpha(), (ROW_ICON_SIZE, ROW_ICON_SIZE)
                )
                icon.fill((*ROW_ICON_COLOR, 0), special_flags=pygame.BLEND_RGBA_ADD)
                self._row_icons[key] = icon

        self._back_label = text.pixel_label("VOLVER", BUTTON_TEXT_COLOR, BUTTON_TEXT_SCALE)
        # Page switch: "2x2x2 >" on the first page, "< CONTROLES" on the second.
        self._page_labels = [
            text.pixel_label("2x2x2 >", BUTTON_TEXT_COLOR, BUTTON_TEXT_SCALE),
            text.pixel_label("< CONTROLES", BUTTON_TEXT_COLOR, BUTTON_TEXT_SCALE),
        ]
        page_button_width = round(max(PAGE_BUTTON_WIDTH, *(label.get_width() + 16 for label in self._page_labels)))
        total_width = BACK_BUTTON_WIDTH + PAGE_BUTTON_GAP + page_button_width
        left = (settings.VIRTUAL_WIDTH - total_width) / 2
        bottom = settings.VIRTUAL_HEIGHT - BACK_BUTTON_BOTTOM_MARGIN
        self._back_button_rect = pygame.Rect(0, 0, BACK_BUTTON_WIDTH, BACK_BUTTON_HEIGHT)
        self._back_button_rect.left = round(left)
        self._back_button_rect.bottom = bottom
        self._page_button_rect = pygame.Rect(0, 0, page_button_width, BACK_BUTTON_HEIGHT)
        self._page_button_rect.left = self._back_button_rect.right + PAGE_BUTTON_GAP
        self._page_button_rect.bottom = bottom

    def exit(self) -> None:
        pass

    def _virtual_position(self, data: MouseClickData) -> Tuple[float, float]:
        x, y = data.position
        return (
            x * settings.VIRTUAL_WIDTH / settings.WINDOW_WIDTH,
            y * settings.VIRTUAL_HEIGHT / settings.WINDOW_HEIGHT,
        )

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if input_id == "mouse_click" and isinstance(input_data, MouseClickData):
            if input_data.pressed:
                position = self._virtual_position(input_data)
                if self._back_button_rect.collidepoint(position):
                    self.state_machine.change("menu")
                elif self._page_button_rect.collidepoint(position):
                    self._page = 1 - self._page

        elif input_id == "mouse_motion" and isinstance(input_data, MouseMotionData):
            x, y = input_data.position
            self._last_mouse_pos = (
                x * settings.VIRTUAL_WIDTH / settings.WINDOW_WIDTH,
                y * settings.VIRTUAL_HEIGHT / settings.WINDOW_HEIGHT,
            )

    def update(self, dt: float) -> None:
        pass

    def _draw_rows(self, surface: pygame.Surface, rows: Tuple[_Row, ...], top: float) -> None:
        y = top
        first_header = True

        for row in rows:
            x = LEFT_MARGIN if row.kind == "header" else LEFT_MARGIN + INDENT
            if row.kind == "header":
                if not first_header:
                    y += HEADER_EXTRA_GAP
                first_header = False

            for icon_key in row.icons:
                icon = self._row_icons[icon_key]
                surface.blit(icon, (x, y))
                x += ROW_ICON_SIZE + ROW_ICON_GAP

            font_key, color = ("body_bold", COLOR_HEADING) if row.kind == "header" else ("body", COLOR_TEXT)
            for line in _wrap(row.text, font_key, settings.VIRTUAL_WIDTH - LEFT_MARGIN - x):
                # Vertically centered on the icon when there is one.
                line_y = y + (ROW_ICON_SIZE - text.text_size(line, font_key)[1]) / 2 if row.icons else y
                text.render_text(line, font_key, x, line_y, color)
                y += LINE_HEIGHT

    def _draw_button(self, surface: pygame.Surface, rect: pygame.Rect, label: text.PixelLabel) -> None:
        is_hovered = self._last_mouse_pos is not None and rect.collidepoint(self._last_mouse_pos)
        background_color = BUTTON_HOVER_COLOR if is_hovered else BUTTON_COLOR

        pygame.draw.rect(surface, background_color, rect, border_radius=6)
        pygame.draw.rect(surface, BUTTON_BORDER_COLOR, rect, width=1, border_radius=6)
        label.draw(*rect.center)

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(COLOR_BG)
        title_surface = self._title_surfaces[self._page]
        title_surface.draw(settings.VIRTUAL_WIDTH / 2, TOP_MARGIN, anchor="midtop")
        self._draw_rows(surface, _PAGES[self._page][1], TOP_MARGIN + title_surface.get_height() + 8)
        self._draw_button(surface, self._back_button_rect, self._back_label)
        self._draw_button(surface, self._page_button_rect, self._page_labels[self._page])
