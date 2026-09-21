"""
StartState: title screen and level selection. Navigate with UP/DOWN,
ENTER to play the highlighted level, ESC to quit.
"""
from typing import Any, Dict, List, Tuple

import pygame

from gale.input_handler import InputData
from gale.state import BaseState
from gale.text import render_text

import settings
from src.levels import LEVELS

# render_text() no envuelve texto (dibuja todo en una sola linea, ver
# gale.text) -- la descripcion mas larga del catalogo (El Planeador, ver
# src/levels.py) mide ~848px con la fuente "hud" contra un canvas de
# 624px, así que centrada quedaba 112px fuera de cada borde: invisible,
# no solo recortada. _wrap_description evita eso partiendola en lineas
# que sí entran en pantalla.
_DESCRIPTION_MAX_WIDTH = settings.VIRTUAL_WIDTH - 60
_DESCRIPTION_LINE_HEIGHT = 16


def _wrap_description(text: str, font: pygame.font.Font, max_width: int) -> List[str]:
    words = text.split(" ")
    lines: List[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if font.size(candidate)[0] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


class StartState(BaseState):
    def __init__(self, state_machine, game) -> None:
        super().__init__(state_machine)
        self.game = game
        self.selected_index = 0

    def enter(self, *args: Tuple[Any], **kwargs: Dict[str, Any]) -> None:
        self.selected_index = 0
        # Envuelto una sola vez (no cambia entre frames) para las
        # descripciones de TODOS los niveles, no solo el seleccionado --
        # asi la fila reserva siempre el mismo alto (el del nivel con mas
        # lineas) y la lista no salta de lugar al cambiar la seleccion.
        self._wrapped_descriptions = [
            _wrap_description(level.description, settings.FONTS["hud"], _DESCRIPTION_MAX_WIDTH)
            for level in LEVELS
        ]
        self._max_description_lines = max(len(lines) for lines in self._wrapped_descriptions)

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if not getattr(input_data, "pressed", False):
            return

        if input_id == "nav_up":
            self.selected_index = (self.selected_index - 1) % len(LEVELS)
        elif input_id == "nav_down":
            self.selected_index = (self.selected_index + 1) % len(LEVELS)
        elif input_id == "confirm":
            self.state_machine.change("play", level_index=self.selected_index)
        elif input_id == "back":
            self.game.quit()

    def update(self, dt: float) -> None:
        pass

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(settings.BACKGROUND_COLOR)

        render_text(
            surface,
            "CONWAY'S PUZZLE",
            settings.FONTS["title"],
            settings.VIRTUAL_WIDTH // 2,
            50,
            settings.HUD_ACCENT_COLOR,
            center=True,
        )

        y = 120
        for index, level in enumerate(LEVELS):
            selected = index == self.selected_index
            color = settings.MENU_HIGHLIGHT_COLOR if selected else settings.HUD_TEXT_COLOR
            prefix = "> " if selected else "  "
            render_text(
                surface,
                f"{prefix}{index + 1}. {level.name}",
                settings.FONTS["menu"],
                settings.VIRTUAL_WIDTH // 2,
                y,
                color,
                center=True,
            )
            if selected:
                for line_index, line in enumerate(self._wrapped_descriptions[index]):
                    render_text(
                        surface,
                        line,
                        settings.FONTS["hud"],
                        settings.VIRTUAL_WIDTH // 2,
                        y + 18 + line_index * _DESCRIPTION_LINE_HEIGHT,
                        settings.HUD_TEXT_COLOR,
                        center=True,
                    )
            # Alto fijo por fila (siempre el del nivel con mas lineas de
            # descripcion, no solo el seleccionado) para que la lista no
            # salte de lugar al cambiar de seleccion.
            y += 18 + self._max_description_lines * _DESCRIPTION_LINE_HEIGHT + 12

        render_text(
            surface,
            "Flechas: navegar   ENTER: jugar   ESC: salir",
            settings.FONTS["hud"],
            settings.VIRTUAL_WIDTH // 2,
            settings.VIRTUAL_HEIGHT - 20,
            settings.HUD_TEXT_COLOR,
            center=True,
        )
