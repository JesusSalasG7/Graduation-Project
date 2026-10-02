"""
This file contains the class GuideState: a paged "how to play" guide
opened from the title screen (StartState's "Guía" button, or the G
key). It explains the controls and goal, what each of the 8 elements
does in combat, and what every combo (match size, Catálisis,
Resonancia, cascades) is worth. Left/right arrows or the on-screen
buttons change pages; Enter, G or "Volver" go back to the title screen.

Every number shown (time limit, points, multipliers, enemy ramp) is
read from the same constants the game uses, so rebalancing the game
keeps the guide accurate. The per-element damage/heal values live
inside lambdas in src/combat/elements.py and can't be read back, so
they're restated in ELEMENT_EFFECTS below -- keep both in sync.
"""

from typing import Any, List, Optional, Tuple

import pygame

from gale.input_handler import InputData
from gale.state import BaseState

import settings
from src.text import render_text
from src.board.tile import TileKind
from src.combat.combat_manager import ENEMY_RAMP_TURNS
from src.combat.elements import DAMAGE_MULTIPLIER, DAMAGE_MULTIPLIER_MAX, ELEMENTS
from src.states.play_state import HINT_DELAY

TEXT_COLOR = (235, 235, 240)
DIM_COLOR = (170, 165, 185)
ACCENT_COLOR = (255, 210, 80)
PANEL_COLOR = (30, 24, 40)
BORDER_COLOR = (150, 145, 160)

MARGIN_X = 28
CONTENT_TOP = 104
BODY_LINE_HEIGHT = 19
ITEM_GAP = 10

NAV_BUTTON_SIZE = (140, 40)
NAV_BUTTON_GAP = 12
NAV_LABELS = ("< Anterior", "Volver", "Siguiente >")

ICON_SIZE = 56
ELEMENT_ROW_HEIGHT = 96

# Efecto de cada elemento con un match de 3 fichas (multiplicador x1),
# en el mismo orden que TileKind -- ver src/combat/elements.py.
ELEMENT_EFFECTS = {
    TileKind.FIRE: "18 de daño al enemigo.",
    TileKind.WATER: "Te cura 15 puntos de vida.",
    TileKind.EARTH: "12 de daño y el próximo ataque del enemigo hace la mitad.",
    TileKind.AIR: "10 de daño al enemigo.",
    TileKind.ELECTRICITY: "12 de daño y 30% de probabilidad de aturdirlo: pierde su próximo turno.",
    TileKind.ICE: "8 de daño y el próximo ataque del enemigo hace la mitad.",
    TileKind.MAGIC: "Entre 8 y 24 de daño, con 20% de probabilidad de crítico (daño doble).",
    TileKind.DARKNESS: "16 de daño al enemigo.",
}


def _format_multiplier(value: float) -> str:
    return f"x{value:g}".replace(".", ",")


# Cada página es (título, contenido). El contenido es una lista de
# (encabezado, texto) -- texto corrido bajo un encabezado dorado -- o
# una lista de TileKind, que se dibuja como la tabla de elementos con
# el ícono de cada ficha (ver GuideState._render_elements).
PAGES: List[Tuple[str, List[Any]]] = [
    (
        "Cómo jugar",
        [
            ("Objetivo", f"Derrota al enemigo antes de que pasen {settings.COMBAT_TIME_LIMIT} segundos. "
                         "Si tu vida o el tiempo llegan a cero, pierdes."),
            ("Mover fichas", "Haz clic en una ficha y luego en otra vecina (arriba, abajo, "
                             "izquierda o derecha) para intercambiarlas."),
            ("Formar líneas", "Si el intercambio alinea 3 o más fichas del mismo elemento, "
                              "se destruyen y lanzas el hechizo de ese elemento. Si no forma "
                              "ninguna línea, las fichas vuelven a su lugar y no pierdes el turno."),
            ("Turno del enemigo", "Cuando tu jugada termina de resolverse, el enemigo ataca "
                                  "con uno de los mismos 8 elementos. Tiene más vida que tú y "
                                  f"cada {ENEMY_RAMP_TURNS} turnos sus ataques se vuelven más fuertes."),
            ("Pista", f"Si pasas {HINT_DELAY:g} segundos sin jugar, se resaltan dos fichas "
                      "que puedes intercambiar."),
        ],
    ),
    ("Elementos (1 de 2)", list(TileKind)[:4]),
    ("Elementos (2 de 2)", list(TileKind)[4:]),
    (
        "Combos",
        [
            ("Línea de 3", f"El hechizo del elemento con su efecto normal "
                           f"({_format_multiplier(DAMAGE_MULTIPLIER[3])})."),
            ("Línea de 4", f"Efecto {_format_multiplier(DAMAGE_MULTIPLIER[4])} "
                           "y además activa una Catálisis."),
            ("Línea de 5 o más", f"Efecto {_format_multiplier(DAMAGE_MULTIPLIER_MAX)} "
                                 "y además activa una Catálisis."),
            ("Formas en L o T", "Cuentan como dos líneas: cada una lanza su propio hechizo."),
            ("Cascadas", "Si las fichas que caen forman nuevas líneas, también lanzan "
                         "su hechizo, dentro del mismo turno."),
        ],
    ),
    (
        "Catálisis y puntaje",
        [
            ("Catálisis", "Una línea de 4 o más fichas destruye toda su fila o columna, "
                          "sin importar el elemento de cada ficha, y suma "
                          f"+{settings.CATALYSIS_BONUS} puntos. Las fichas extra suman puntos, "
                          "pero no lanzan hechizos."),
            ("Resonancia", f"En una Catálisis, +{settings.RESONANCE_BONUS_PER_KIND} puntos por cada "
                           "elemento que aparezca 2 o más veces en la línea destruida."),
            ("Puntaje", f"Cada ficha destruida suma {settings.POINTS_PER_TILE} puntos."),
        ],
    ),
]


def _readable(color: Tuple[int, int, int]) -> Tuple[int, int, int]:
    """Aclara los colores de elemento demasiado oscuros para leerse
    sobre el fondo de la guía (p. ej. Oscuridad), mezclándolos con
    blanco; el resto queda igual."""
    if sum(color) / 3 >= 110:
        return color
    return tuple(round(c + (255 - c) * 0.45) for c in color)


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


class GuideState(BaseState):
    def enter(self, **_enter_params) -> None:
        self.page = 0
        self.nav_button_rects: List[pygame.Rect] = []
        width, height = NAV_BUTTON_SIZE
        total_width = len(NAV_LABELS) * width + (len(NAV_LABELS) - 1) * NAV_BUTTON_GAP
        left = (settings.VIRTUAL_WIDTH - total_width) // 2
        for index in range(len(NAV_LABELS)):
            rect = pygame.Rect(0, 0, width, height)
            rect.topleft = (left + index * (width + NAV_BUTTON_GAP), settings.VIRTUAL_HEIGHT - 64)
            self.nav_button_rects.append(rect)

        self.icons = {
            kind: pygame.transform.smoothscale(settings.TILE_SPRITES[kind.value], (ICON_SIZE, ICON_SIZE))
            for kind in TileKind
        }

    # -- Navegación -------------------------------------------------------

    def _change_page(self, delta: int) -> None:
        self.page = max(0, min(len(PAGES) - 1, self.page + delta))

    def _nav_enabled(self, index: int) -> bool:
        if index == 0:
            return self.page > 0
        if index == 2:
            return self.page < len(PAGES) - 1
        return True

    def _activate_nav(self, index: int) -> None:
        if not self._nav_enabled(index):
            return
        if index == 0:
            self._change_page(-1)
        elif index == 2:
            self._change_page(1)
        else:
            self.state_machine.change("start")

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if not input_data.pressed:
            return

        if input_id == "click":
            pos_x = input_data.position[0] * settings.VIRTUAL_WIDTH // settings.WINDOW_WIDTH
            pos_y = input_data.position[1] * settings.VIRTUAL_HEIGHT // settings.WINDOW_HEIGHT
            for index, rect in enumerate(self.nav_button_rects):
                if rect.collidepoint(pos_x, pos_y):
                    self._activate_nav(index)
                    return
        elif input_id == "left":
            self._change_page(-1)
        elif input_id == "right":
            self._change_page(1)
        elif input_id in ("enter", "guide"):
            self.state_machine.change("start")

    # -- Render -------------------------------------------------------------

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(settings.BACKGROUND_COLOR)

        title, content = PAGES[self.page]
        render_text(
            surface, "Guía de juego", settings.FONTS["small"], settings.VIRTUAL_WIDTH // 2, 28,
            DIM_COLOR, center=True, shadowed=True,
        )
        render_text(
            surface, title, settings.FONTS["medium"], settings.VIRTUAL_WIDTH // 2, 62,
            ACCENT_COLOR, center=True, shadowed=True,
        )
        pygame.draw.line(
            surface, BORDER_COLOR, (MARGIN_X, 86), (settings.VIRTUAL_WIDTH - MARGIN_X, 86), 1
        )

        if isinstance(content[0], TileKind):
            self._render_elements(surface, content)
        else:
            self._render_items(surface, content)

        render_text(
            surface, f"Página {self.page + 1} de {len(PAGES)}", settings.FONTS["tiny"],
            settings.VIRTUAL_WIDTH // 2, settings.VIRTUAL_HEIGHT - 82, DIM_COLOR, center=True,
        )
        self._render_nav_buttons(surface)

    def _render_items(self, surface: pygame.Surface, items: List[Tuple[Optional[str], str]]) -> None:
        max_width = settings.VIRTUAL_WIDTH - 2 * MARGIN_X
        y = CONTENT_TOP
        for heading, body in items:
            if heading:
                render_text(surface, heading, settings.FONTS["small"], MARGIN_X, y, ACCENT_COLOR, shadowed=True)
                y += 24
            for line in _wrap(body, settings.FONTS["tiny"], max_width):
                render_text(surface, line, settings.FONTS["tiny"], MARGIN_X, y, TEXT_COLOR)
                y += BODY_LINE_HEIGHT
            y += ITEM_GAP

    def _render_elements(self, surface: pygame.Surface, kinds: List[TileKind]) -> None:
        render_text(
            surface, "Efecto de cada elemento con una línea de 3 fichas:", settings.FONTS["tiny"],
            MARGIN_X, CONTENT_TOP - 6, DIM_COLOR,
        )
        text_x = MARGIN_X + ICON_SIZE + 12
        max_width = settings.VIRTUAL_WIDTH - text_x - MARGIN_X
        y = CONTENT_TOP + 26
        for kind in kinds:
            surface.blit(self.icons[kind], (MARGIN_X, y))
            render_text(
                surface, ELEMENTS[kind]["name"], settings.FONTS["small"], text_x, y,
                _readable(ELEMENTS[kind]["color"]), shadowed=True,
            )
            line_y = y + 26
            for line in _wrap(ELEMENT_EFFECTS[kind], settings.FONTS["tiny"], max_width):
                render_text(surface, line, settings.FONTS["tiny"], text_x, line_y, TEXT_COLOR)
                line_y += BODY_LINE_HEIGHT - 2
            y += ELEMENT_ROW_HEIGHT

    def _render_nav_buttons(self, surface: pygame.Surface) -> None:
        for index, (label, rect) in enumerate(zip(NAV_LABELS, self.nav_button_rects)):
            enabled = self._nav_enabled(index)
            border_color = ACCENT_COLOR if index == 1 else BORDER_COLOR
            pygame.draw.rect(surface, PANEL_COLOR, rect, border_radius=8)
            pygame.draw.rect(
                surface, border_color if enabled else (70, 65, 80), rect, width=3, border_radius=8
            )
            render_text(
                surface, label, settings.FONTS["tiny"], rect.centerx, rect.centery,
                TEXT_COLOR if enabled else (100, 95, 110), center=True, shadowed=enabled,
            )
