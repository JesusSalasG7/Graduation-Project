
import pygame

from gale.input_handler import InputData
from gale.state import BaseState
from gale.text import render_text

import settings
from src.states import game_states

TITLE_COLOR = (245, 191, 66)
TEXT_COLOR = (197, 195, 198)
PROMPT_COLOR = (150, 148, 150)

MAX_TEXT_WIDTH = 360
LINE_HEIGHT = 11
MAX_LINES_PER_PAGE = 6

SCENE_TITLE = "El Cuadro que No Deja Pasar"

# Guion de la escena: cada elemento es un "beat" que se ajusta (word-wrap)
# y se pagina automáticamente según lo que quepa en pantalla.
SCRIPT = [
    "\"¿Otro intruso buscando la llave...? Je, je, je. Muchos me miran, "
    "pero muy pocos logran verme realmente.\"",

    "\"Te propongo un acertijo, pequeño saltarín: Facciones de hombre, "
    "semblante de señor... pero quien guarda tu premio no es ningún varón. "
    "Bajo este rostro de falsa rudeza, respira en silencio una oculta belleza. "
    "Si quieres la llave, rompe mi máscara, pieza por pieza.\"",

    "\"Vamos... demuéstrame tu ingenio. Llevo siglos esperando a alguien "
    "digno de ver lo que hay detrás de esta pintura.\"",

    "El retrato oculta una doble identidad. Desarma el rostro masculino "
    "para descubrir a la mujer y obtener la llave."
]


def _wrap(text: str, font: pygame.font.Font, max_width: int) -> list:
    """Parte `text` en líneas que no excedan `max_width` píxeles."""
    words = text.split(" ")
    lines = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if not current or font.size(candidate)[0] <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _paginate(beats: list, font: pygame.font.Font, max_width: int, max_lines: int) -> list:
    """Ajusta cada beat y lo reparte en páginas de a lo sumo `max_lines` líneas."""
    pages = []
    for beat in beats:
        lines = _wrap(beat, font, max_width)
        for start in range(0, len(lines), max_lines):
            pages.append(lines[start:start + max_lines])
    return pages


class WheresTheKeyState(BaseState):
    """
    Escena "El Cuadro que No Deja Pasar": cutscene del retrato viviente que
    bloquea el paso a la llave, seguida de la instrucción del puzzle.

    Se muestra página por página (ENTER avanza); al llegar a la última
    página, ENTER entra a PuzzleState.
    """

    def enter(self, player) -> None:
        self.player = player
        self.pages = _paginate(
            SCRIPT, settings.FONTS["small"], MAX_TEXT_WIDTH, MAX_LINES_PER_PAGE
        )
        self.page_index = 0

    def render(self, surface: pygame.Surface) -> None:
        surface.fill((51, 25, 102))

        render_text(
            surface,
            SCENE_TITLE,
            settings.FONTS["medium"],
            settings.VIRTUAL_WIDTH // 2,
            18,
            TITLE_COLOR,
            center=True,
            shadowed=True,
        )

        lines = self.pages[self.page_index]
        top = settings.VIRTUAL_HEIGHT // 2 - (len(lines) * LINE_HEIGHT) // 2
        for i, line in enumerate(lines):
            render_text(
                surface,
                line,
                settings.FONTS["small"],
                settings.VIRTUAL_WIDTH // 2,
                top + i * LINE_HEIGHT,
                TEXT_COLOR,
                center=True,
                shadowed=True,
            )

        is_last_page = self.page_index == len(self.pages) - 1
        render_text(
            surface,
            "Presiona ENTER para comenzar" if is_last_page else "Presiona ENTER para continuar",
            settings.FONTS["small"],
            settings.VIRTUAL_WIDTH // 2,
            settings.VIRTUAL_HEIGHT - 12,
            PROMPT_COLOR,
            center=True,
            shadowed=True,
        )

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if input_id != "enter" or not input_data.pressed:
            return

        if self.page_index < len(self.pages) - 1:
            self.page_index += 1
        else:
            self.state_machine.pop()
            self.state_machine.push(
                game_states.PuzzleState(self.state_machine), player=self.player
            )
