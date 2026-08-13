"""
Instructions screen: explains every control and button currently in
the game (see PlayState) -- camera, layer moves, and the icon buttons
(Shuffle/Auto/Eye/Search/Undo/Redo). Reachable from MenuState's
"Instructions" button; "Back" returns to it.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import pygame

from gale.conf import settings
from gale.input_handler import InputData, MouseClickData, MouseMotionData
from gale.state import BaseState

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
BUTTON_TEXT_SCALE = 2

BACK_BUTTON_WIDTH = 112
BACK_BUTTON_HEIGHT = 22
BACK_BUTTON_BOTTOM_MARGIN = 8

BUTTON_COLOR = pygame.Color(255, 255, 255)
BUTTON_HOVER_COLOR = pygame.Color(210, 225, 250)
BUTTON_BORDER_COLOR = pygame.Color(170, 170, 178)
BUTTON_TEXT_COLOR = (18, 18, 22)


@dataclass
class _Row:
    kind: str  # "header" or "line"
    text: str
    icons: Tuple[str, ...] = field(default_factory=tuple)  # keys into settings.TEXTURES


# The actual list of controls/buttons this file documents -- keep in
# sync with src/states/play_state.py whenever a control changes there.
_ROWS: Tuple[_Row, ...] = (
    _Row("header", "CAMARA"),
    _Row("line", "Arrastrar el mouse, o las flechas: rotar la camara"),
    _Row("header", "MOVIMIENTOS"),
    _Row("line", "U D L R F B: girar esa cara (sentido horario)"),
    _Row("line", "+ Shift: sentido antihorario"),
    _Row("line", "+ Alt: capa doble   |   + Alt + Shift: capa doble antihoraria"),
    _Row("line", "M E S: capas del medio (+ Shift: antihorario)"),
    _Row("header", "BOTONES"),
    _Row("line", "Aplica 20 movimientos al azar, animados", icons=("shuffle",)),
    _Row("line", "Mezcla y activa el temporizador (abajo a la derecha)", icons=("auto",)),
    _Row("line", "Guia: marca que cara es U/D/L/R/F/B", icons=("eye_open",)),
    _Row("line", "Busca un bloque 2x2x2 conocido (desafio A03)", icons=("search",)),
    _Row("line", "Deshacer / rehacer el ultimo movimiento", icons=("undo", "redo")),
    _Row("header", "OTROS"),
    _Row("line", "Esc: salir del juego"),
)


class InstructionsState(BaseState):
    def enter(self, *args: Tuple[Any], **kwargs: Dict[str, Any]) -> None:
        self._last_mouse_pos: Optional[Tuple[float, float]] = None

        self._title_font = settings.FONTS["pixel_title"]
        self._body_font = settings.FONTS["body"]
        self._heading_font = settings.FONTS["body_bold"]
        self._button_font = settings.FONTS["pixel_button"]

        self._title_surface = self._render_pixel(self._title_font, "INSTRUCCIONES", (255, 255, 255), TITLE_SCALE)
        self._title_rect = self._title_surface.get_rect(
            centerx=settings.VIRTUAL_WIDTH / 2, top=TOP_MARGIN
        )

        # Every button icon (shuffle.png, eye_open.png, ...) is a solid
        # black shape on a transparent background -- fine on the light
        # buttons in PlayState, but nearly invisible on this screen's
        # dark background. BLEND_RGBA_ADD adds RGB (with alpha 0, so it
        # doesn't touch the alpha channel) on top of the icon's own
        # black pixels, recoloring the shape to `ROW_ICON_COLOR` while
        # keeping its original antialiased silhouette intact.
        self._row_icons: Dict[str, pygame.Surface] = {}
        for row in _ROWS:
            for key in row.icons:
                if key in self._row_icons:
                    continue
                icon = pygame.transform.smoothscale(
                    settings.TEXTURES[key].convert_alpha(), (ROW_ICON_SIZE, ROW_ICON_SIZE)
                )
                icon.fill((*ROW_ICON_COLOR, 0), special_flags=pygame.BLEND_RGBA_ADD)
                self._row_icons[key] = icon

        self._back_label = self._render_pixel(self._button_font, "VOLVER", BUTTON_TEXT_COLOR, BUTTON_TEXT_SCALE)
        self._back_button_rect = pygame.Rect(0, 0, BACK_BUTTON_WIDTH, BACK_BUTTON_HEIGHT)
        self._back_button_rect.centerx = settings.VIRTUAL_WIDTH / 2
        self._back_button_rect.bottom = settings.VIRTUAL_HEIGHT - BACK_BUTTON_BOTTOM_MARGIN

    def exit(self) -> None:
        pass

    def _render_pixel(self, font: pygame.font.Font, text: str, color, scale: int) -> pygame.Surface:
        """Same blocky/pixel-art rendering MenuState uses for its title and buttons, kept local so this state doesn't depend on menu_state."""
        small = font.render(text, False, color)
        size = (max(1, small.get_width() * scale), max(1, small.get_height() * scale))
        return pygame.transform.scale(small, size)

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

        elif input_id == "mouse_motion" and isinstance(input_data, MouseMotionData):
            x, y = input_data.position
            self._last_mouse_pos = (
                x * settings.VIRTUAL_WIDTH / settings.WINDOW_WIDTH,
                y * settings.VIRTUAL_HEIGHT / settings.WINDOW_HEIGHT,
            )

    def update(self, dt: float) -> None:
        pass

    def _draw_rows(self, surface: pygame.Surface) -> None:
        y = self._title_rect.bottom + 8
        first_header = True

        for row in _ROWS:
            if row.kind == "header":
                if not first_header:
                    y += HEADER_EXTRA_GAP
                first_header = False
                text_surface = self._heading_font.render(row.text, True, COLOR_HEADING)
                surface.blit(text_surface, (LEFT_MARGIN, y))
                y += LINE_HEIGHT
                continue

            x = LEFT_MARGIN + INDENT
            for icon_key in row.icons:
                icon = self._row_icons[icon_key]
                surface.blit(icon, (x, y))
                x += ROW_ICON_SIZE + ROW_ICON_GAP

            text_surface = self._body_font.render(row.text, True, COLOR_TEXT)
            surface.blit(text_surface, (x, y + (ROW_ICON_SIZE - text_surface.get_height()) / 2 if row.icons else y))
            y += LINE_HEIGHT

    def _draw_back_button(self, surface: pygame.Surface) -> None:
        is_hovered = (
            self._last_mouse_pos is not None
            and self._back_button_rect.collidepoint(self._last_mouse_pos)
        )
        background_color = BUTTON_HOVER_COLOR if is_hovered else BUTTON_COLOR

        pygame.draw.rect(surface, background_color, self._back_button_rect, border_radius=6)
        pygame.draw.rect(surface, BUTTON_BORDER_COLOR, self._back_button_rect, width=1, border_radius=6)
        surface.blit(self._back_label, self._back_label.get_rect(center=self._back_button_rect.center))

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(COLOR_BG)
        surface.blit(self._title_surface, self._title_rect)
        self._draw_rows(surface)
        self._draw_back_button(surface)
