"""
LevelIntroState: the briefing shown every time the player enters a level
(pushed on ConwayGame.overlay_stack by PlayState.enter, and again with I
from inside the level). It spells out, for that specific level, the goal,
what the player has to work with, what to do step by step, and a hint
pointing to the matching demo in the guide.

ENTER closes it and starts playing; G opens the full guide on top of it
(closing the guide comes back here); ESC goes back to the level menu.
The texts live in BRIEFINGS below, in the same order as src/levels.py --
keep them in sync if a level changes.
"""
from typing import Any, List, Tuple

import pygame

from gale.input_handler import InputData

import settings
from src import text as text_layer
from src.levels import LEVELS
from src.text import render_text

MARGIN_X = 24
LINE_HEIGHT = 15
HEADING_HEIGHT = 17
SECTION_GAP = 7
STEP_INDENT = 28

DIM_COLOR = pygame.Color(150, 150, 170)

# (objetivo, pasos, pista) de cada nivel.
BRIEFINGS: List[Tuple[str, List[str], str]] = [
    (
        "Que al menos una célula viva llegue a la franja turquesa vertical. Ganas en "
        "cuanto una célula esté dentro de ella.",
        [
            "Haz clic en casillas vacías a la izquierda de la franja para poner células "
            "verdes. Otro clic sobre una la quita.",
            "No las pongas sueltas: una célula sola muere. Ponlas juntas, en grupo, para "
            "que se reproduzcan y el grupo crezca.",
            "Presiona ESPACIO y observa cómo el grupo cambia y se expande hacia la franja.",
            "Si todo muere o se queda quieto lejos de la franja, presiona ENTER y prueba "
            "otro diseño.",
        ],
        "5 células en forma de R-pentominó crecen mucho. Míralo en la guía (G): "
        "'Así se ve resolverlo: nivel 1'.",
    ),
    (
        "Que una célula viva llegue a la zona turquesa del extremo derecho del pasillo.",
        [
            "Las paredes grises de arriba y abajo no pueden tener vida: lo que choca con "
            "ellas se deforma o muere.",
            "Pon tu diseño en el lado izquierdo del pasillo. Con 14 células no llegas "
            "creciendo: necesitas un patrón que viaje solo hacia la derecha (una 'nave').",
            "Presiona ESPACIO: la nave debe avanzar recto, sin tocar las paredes.",
            "Si choca o se desarma, presiona ENTER y ajusta su posición o su forma.",
        ],
        "Una nave ligera de 9 células cruza el pasillo. Míralo en la guía (G): "
        "'Así se ve resolverlo: nivel 2'.",
    ),
    (
        "Eliminar el bloque rojo del centro: ganas cuando sus 4 casillas quedan vacías.",
        [
            "Solo, el bloque es estable y nunca cambia. No puedes poner células encima de él.",
            "Pon tus células pegadas al bloque (junto a un lado o una esquina) para "
            "cambiar la cantidad de vecinas de sus células.",
            "Presiona S para avanzar generación por generación y ver cómo se deforma, o "
            "ESPACIO para verlo seguido.",
            "Si el bloque se recompone o queda algo rojo estable, presiona ENTER y prueba "
            "en otra posición.",
        ],
        "Basta con 1 célula bien ubicada. Míralo en la guía (G): 'Así se ve resolverlo: "
        "nivel 3'.",
    ),
    (
        "Que una célula viva llegue a la zona turquesa de la parte de abajo.",
        [
            "Solo tienes 5 células: justo las de un planeador, una figura que viaja sola "
            "en diagonal (su forma está en la guía, 'Patrones útiles').",
            "Constrúyelo en la parte de arriba, orientado para que baje hacia la zona "
            "(abajo-derecha o abajo-izquierda según dónde lo pongas).",
            "Presiona ESPACIO: debe recuperar su forma cada 4 generaciones, una casilla "
            "más abajo en diagonal.",
            "Si no apunta a la zona o se deforma, presiona ENTER y corrige su forma o su "
            "posición.",
        ],
        "Míralo en la guía (G): 'Así se ve resolverlo: nivel 4'.",
    ),
]


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


class LevelIntroState:
    def __init__(self, game) -> None:
        self.game = game

    def enter(self, level_index: int = 0, *args: Tuple[Any], **kwargs: Any) -> None:
        self.level_index = level_index
        self.level = LEVELS[level_index]

    def exit(self) -> None:
        pass

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if not getattr(input_data, "pressed", False):
            return

        if input_id in ("confirm", "level_info"):
            self.game.hide_overlay()
        elif input_id == "open_guide":
            self.game.show_guide()
        elif input_id == "back":
            self.game.hide_overlay()
            self.game.state_machine.change("start")

    def update(self, dt: float) -> None:
        pass

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(settings.BACKGROUND_COLOR)
        # Tapa por completo el tablero, incluido el texto del HUD ya encolado.
        text_layer.discard_queued()

        center_x = settings.VIRTUAL_WIDTH // 2
        render_text(
            surface, f"NIVEL {self.level_index + 1} DE {len(LEVELS)}", settings.FONTS["hud"],
            center_x, 16, DIM_COLOR, center=True,
        )
        render_text(
            surface, self.level.name, settings.FONTS["banner"], center_x, 38,
            settings.HUD_ACCENT_COLOR, center=True,
        )
        render_text(
            surface, f"Presupuesto: {self.level.budget} células", settings.FONTS["hud"],
            center_x, 60, settings.HUD_TEXT_COLOR, center=True,
        )
        pygame.draw.line(
            surface, settings.GRID_LINE_COLOR, (MARGIN_X, 72), (settings.VIRTUAL_WIDTH - MARGIN_X, 72)
        )

        goal, steps, hint = BRIEFINGS[self.level_index]
        y = self._section(surface, "Tu objetivo", 80)
        y = self._paragraph(surface, goal, MARGIN_X + 8, y) + SECTION_GAP
        y = self._section(surface, "Qué debes hacer", y)
        for number, step in enumerate(steps, start=1):
            render_text(
                surface, f"{number}.", settings.FONTS["hud"], MARGIN_X + 8, y, settings.HUD_ACCENT_COLOR
            )
            y = self._paragraph(surface, step, MARGIN_X + STEP_INDENT, y) + 2
        y += SECTION_GAP - 2
        y = self._section(surface, "Pista", y)
        self._paragraph(surface, hint, MARGIN_X + 8, y)

        pygame.draw.line(
            surface,
            settings.GRID_LINE_COLOR,
            (MARGIN_X, settings.VIRTUAL_HEIGHT - 34),
            (settings.VIRTUAL_WIDTH - MARGIN_X, settings.VIRTUAL_HEIGHT - 34),
        )
        render_text(
            surface,
            "ENTER: empezar   G: guía completa   ESC: menú   (I: ver esto de nuevo)",
            settings.FONTS["hud"],
            center_x,
            settings.VIRTUAL_HEIGHT - 18,
            settings.HUD_ACCENT_COLOR,
            center=True,
        )

    def _section(self, surface: pygame.Surface, title: str, y: int) -> int:
        render_text(surface, title, settings.FONTS["menu"], MARGIN_X, y, settings.HUD_ACCENT_COLOR)
        return y + HEADING_HEIGHT + 3

    def _paragraph(self, surface: pygame.Surface, body: str, x: int, y: int) -> int:
        font = settings.FONTS["hud"]
        for line in _wrap(body, font, settings.VIRTUAL_WIDTH - MARGIN_X - x):
            render_text(surface, line, font, x, y, settings.HUD_TEXT_COLOR)
            y += LINE_HEIGHT
        return y
