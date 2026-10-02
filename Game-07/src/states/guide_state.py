"""
GuideState: a paged "how to play" guide, shown as an overlay (pushed on
ConwayGame.overlay_stack, like VictoryState) so it can be opened with G
both from the level menu and in the middle of a level without losing
the cells the player already placed -- PlayState pauses the simulation
before opening it.

It covers the goal, a step-by-step walkthrough, the controls, the B3/S23
rules, a few useful patterns (drawn as small grids), what each color and
HUD field means, what exactly each level asks for, an animated demo per
level of what solving it should look like (placement, how the cells
evolve, and the victory), and what to check when something seems off.
LEFT/RIGHT change pages; G, ENTER or ESC close.

Level names and budgets are read from src/levels.py; the per-level goal
text lives in LEVEL_GOALS below and the demo captions in DEMO_CAPTIONS --
keep both in sync if a level changes. The demo frames themselves are
precomputed data (src/guide_demos.py), never computed here, so the guide
doesn't ship Conway's rules (the answer to challenge A07).
"""
from typing import Any, List, Sequence, Tuple

import pygame

from gale.input_handler import InputData

import settings
from src import text as text_layer
from src.guide_demos import DEMOS
from src.levels import LEVELS
from src.text import render_text

MARGIN_X = 20
CONTENT_TOP = 72
LINE_HEIGHT = 15
HEADING_HEIGHT = 16
ITEM_GAP = 6
KEY_COLUMN_WIDTH = 130
PATTERN_CELL = 10
SWATCH_SIZE = 12

# Demo animada: mini tablero (mismo mapa que el nivel) y sus tiempos.
DEMO_CELL = 10
DEMO_TOP = 66
DEMO_PLACE_INTERVAL = 0.35  # segundos entre cada célula colocada
DEMO_READY_PAUSE = 1.2  # pausa entre colocar y simular ("presiona ESPACIO")
DEMO_GEN_INTERVAL = 0.18  # segundos por generación
DEMO_WIN_PAUSE = 3.0  # cuánto se muestra la victoria antes de repetir

DIM_COLOR = pygame.Color(150, 150, 170)

# Meta exacta de cada nivel, en el mismo orden que LEVELS.
LEVEL_GOALS = [
    "Gana cuando al menos una célula viva está dentro de la franja turquesa "
    "vertical. Usa grupos de células que crezcan hacia ella: una célula sola muere.",
    "Paredes grises arriba y abajo forman un pasillo. Gana cuando alguna célula "
    "viva llega a la zona turquesa del extremo derecho del pasillo.",
    "Gana cuando las 4 casillas del bloque rojo quedan vacías. Solo, el bloque es "
    "estable y nunca cambia: coloca tus células pegadas a él para desestabilizarlo.",
    "Gana cuando alguna célula viva llega a la zona turquesa de abajo. Con solo 5 "
    "células, arma un planeador (ver 'Patrones útiles') que viaje hasta ella.",
]


# Qué hacer y qué debería verse en la demo de cada nivel (mismo orden
# que LEVELS y src/guide_demos.py).
DEMO_CAPTIONS = [
    (
        "Coloca estas 5 células (un R-pentominó) a la izquierda de la franja y "
        "presiona ESPACIO.",
        "El grupo cambia de forma y crece hacia los lados en cada generación. En la "
        "generación 20 una célula entra en la franja turquesa y aparece NIVEL COMPLETADO.",
    ),
    (
        "Coloca estas 9 células (una nave ligera) al inicio del pasillo y presiona ESPACIO.",
        "La nave alterna entre dos formas y avanza sola hacia la derecha, una casilla "
        "cada 2 generaciones, sin tocar las paredes. Llega a la zona en la generación 33.",
    ),
    (
        "Coloca 1 sola célula pegada al lado izquierdo del bloque rojo y presiona ESPACIO.",
        "El bloque deja de ser estable: se deforma y se encoge, y en la generación 4 ya "
        "no queda ninguna célula roja. Ahí aparece NIVEL COMPLETADO.",
    ),
    (
        "Coloca estas 5 células (un planeador) en la parte de arriba y presiona ESPACIO.",
        "Cada 4 generaciones la figura recupera su forma, una casilla más abajo y a la "
        "derecha. Baja sola hasta la zona turquesa en la generación 33.",
    ),
]


def _text(heading: str, body: str) -> Tuple[str, str, str]:
    return ("text", heading, body)


def _key(key: str, action: str) -> Tuple[str, str, str]:
    return ("key", key, action)


def _pattern(rows: Sequence[str], name: str, body: str) -> Tuple[str, Sequence[str], str, str]:
    return ("pattern", rows, name, body)


def _swatch(color: pygame.Color, body: str) -> Tuple[str, pygame.Color, str]:
    return ("swatch", color, body)


def _demo(level_index: int) -> Tuple[str, int]:
    return ("demo", level_index)


PAGES: List[Tuple[str, List[Tuple[Any, ...]]]] = [
    (
        "Objetivo del juego",
        [
            _text("¿Qué es?", "Un puzle sobre el Juego de la Vida de Conway. Tú no mueves las "
                              "células: solo eliges dónde colocarlas al inicio. Después "
                              "evolucionan solas, generación tras generación, con reglas fijas."),
            _text("Cómo se gana", "Cada nivel tiene una meta: llevar vida hasta la zona objetivo "
                                  "(turquesa) o eliminar las células enemigas (rojas). Cuando la "
                                  "simulación la cumple aparece 'NIVEL COMPLETADO'."),
            _text("Presupuesto", "Cada nivel limita cuántas células puedes colocar. Quitar una "
                                 "célula tuya te devuelve ese punto de presupuesto."),
            _text("No hay derrota", "No hay vidas ni tiempo límite. Si tu diseño no funciona, "
                                    "presiona ENTER para reiniciar el nivel y prueba otro."),
        ],
    ),
    (
        "Paso a paso",
        [
            _text("1. Elige un nivel", "En el menú usa las flechas ARRIBA/ABAJO y presiona ENTER."),
            _text("2. Prepara tu diseño (Gen: 0)", "Haz clic en casillas vacías para poner células "
                                                   "verdes; clic otra vez sobre una para quitarla. "
                                                   "R borra todas las tuyas."),
            _text("3. Inicia la simulación", "ESPACIO la corre de forma continua (y la pausa). "
                                             "S avanza una sola generación para verla con calma."),
            _text("4. Observa", "El contador Gen sube en cada generación y todo el tablero se "
                                "actualiza a la vez según las reglas."),
            _text("5. Ya no se puede editar", "Desde la primera generación no puedes poner ni quitar "
                                              "células. Para cambiar tu diseño, ENTER reinicia."),
            _text("6. Victoria", "Al cumplir la meta la simulación se detiene. ENTER pasa al "
                                 "siguiente nivel; ESC vuelve al menú."),
        ],
    ),
    (
        "Controles",
        [
            _key("Clic izquierdo", "Poner / quitar una célula tuya (solo con Gen: 0)."),
            _key("ESPACIO", "Iniciar o pausar la simulación."),
            _key("S", "Avanzar exactamente una generación (pausa si estaba corriendo)."),
            _key("R", "Quitar todas tus células y recuperar el presupuesto (solo con Gen: 0)."),
            _key("ENTER", "Reiniciar el nivel desde cero."),
            _key("ESC", "Volver al menú de niveles."),
            _key("G", "Abrir o cerrar esta guía (desde el menú o durante un nivel)."),
            _key("I", "Ver otra vez las instrucciones del nivel actual."),
            _key("Menú", "Flechas ARRIBA/ABAJO para elegir nivel, ENTER para jugar, ESC para salir."),
            _key("Guía", "Flechas IZQUIERDA/DERECHA para cambiar de página."),
        ],
    ),
    (
        "Reglas de la vida (B3/S23)",
        [
            _text("Vecinas", "Cada casilla tiene 8 vecinas: arriba, abajo, izquierda, derecha y "
                             "las 4 diagonales. Fuera del borde del tablero no hay vecinas."),
            _text("Sobrevive", "Una célula viva con 2 o 3 vecinas vivas sigue viva."),
            _text("Muere", "Con 0 o 1 vecinas vivas muere por soledad; con 4 o más, por "
                           "sobrepoblación."),
            _text("Nace", "Una casilla vacía con exactamente 3 vecinas vivas se llena con una "
                          "célula nueva."),
            _text("Paredes", "Las paredes grises nunca tienen vida: no puedes colocar células ahí "
                             "y tampoco nacen ahí."),
            _text("Todo a la vez", "Todas las casillas cambian al mismo tiempo, calculadas a partir "
                                   "de la generación anterior."),
        ],
    ),
    (
        "Patrones útiles",
        [
            _pattern(["#"], "Célula sola", "No tiene vecinas: muere en la siguiente generación."),
            _pattern(["##", "##"], "Bloque", "Cada célula tiene 3 vecinas: es estable, nunca cambia."),
            _pattern(["###"], "Parpadeador", "Alterna entre horizontal y vertical cada generación."),
            _pattern([".#.", "..#", "###"], "Planeador",
                     "5 células que avanzan solas en diagonal (aquí hacia abajo a la "
                     "derecha): una casilla cada 4 generaciones. Gíralo o refléjalo "
                     "para cambiar su dirección."),
        ],
    ),
    (
        "Qué ves en pantalla",
        [
            _swatch(settings.PLAYER_CELL_COLOR, "Verde: células vivas (las tuyas y las que nacen)."),
            _swatch(settings.ENEMY_CELL_COLOR, "Rojo: células enemigas (niveles de eliminar)."),
            _swatch(settings.TARGET_ZONE_COLOR, "Turquesa: zona objetivo a la que debes llegar."),
            _swatch(settings.WALL_COLOR, "Gris: pared, nunca puede tener vida."),
            _swatch(settings.CURSOR_COLOR, "Borde blanco: casilla bajo el ratón (solo con Gen: 0)."),
            _text("Barra superior", "Nivel actual · Presupuesto: restantes/total · Gen: "
                                    "generación actual · PAUSA o SIMULANDO."),
            _text("Logros", "Mensajes amarillos arriba a la izquierda (Primer Clic, Eficiencia "
                            "Máxima, Reacción en Cadena). Son opcionales."),
        ],
    ),
    (
        "Los niveles",
        [
            _text(f"{index + 1}. {level.name} (presupuesto: {level.budget})", goal)
            for index, (level, goal) in enumerate(zip(LEVELS, LEVEL_GOALS))
        ],
    ),
    *[
        (f"Así se ve resolverlo: nivel {index + 1}", [_demo(index)])
        for index in range(len(LEVELS))
        if index in DEMOS
    ],
    (
        "Si algo no funciona",
        [
            _text("Gen sube pero ninguna célula cambia", "Las reglas de evolución todavía no están "
                                                         "implementadas en esta versión del juego: es "
                                                         "justo el fallo que se corrige en el desafío."),
            _text("No puedo poner una célula", "La simulación ya empezó (Gen mayor que 0; ENTER "
                                               "reinicia), se acabó el presupuesto, o la casilla es "
                                               "una pared o una célula enemiga."),
            _text("Mis células desaparecen", "Es normal: aisladas mueren por soledad y muy juntas "
                                             "por sobrepoblación. Repasa 'Reglas' y 'Patrones útiles'."),
            _text("No se cumple la meta", "La victoria se revisa después de cada generación. Si el "
                                          "patrón se estabiliza lejos de la meta, reinicia con ENTER."),
            _text("¿Cómo sé si va bien?", "Compara con las páginas 'Así se ve resolverlo': con el "
                                          "mismo diseño, tu tablero debe cambiar exactamente igual."),
        ],
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


class GuideState:
    def __init__(self, game) -> None:
        self.game = game

    def enter(self, *args: Tuple[Any], **kwargs: Any) -> None:
        self._set_page(0)

    def _set_page(self, page: int) -> None:
        self.page = page
        self._restart_demo()

    # -- Demo animada ---------------------------------------------------------
    #
    # Fases: "place" (las células aparecen una a una, Gen 0), "ready"
    # (pausa antes de simular), "run" (una generación cada
    # DEMO_GEN_INTERVAL) y "won" (se muestra la victoria y se repite).

    def _restart_demo(self) -> None:
        self.demo_phase = "place"
        self.demo_timer = 0.0
        self.demo_placed = 0
        self.demo_generation = 0

    def _update_demo(self, dt: float, level_index: int) -> None:
        placed, frames = DEMOS[level_index]
        self.demo_timer += dt
        if self.demo_phase == "place":
            while self.demo_timer >= DEMO_PLACE_INTERVAL and self.demo_placed < len(placed):
                self.demo_timer -= DEMO_PLACE_INTERVAL
                self.demo_placed += 1
            if self.demo_placed == len(placed):
                self.demo_phase, self.demo_timer = "ready", 0.0
        elif self.demo_phase == "ready":
            if self.demo_timer >= DEMO_READY_PAUSE:
                self.demo_phase, self.demo_timer = "run", 0.0
        elif self.demo_phase == "run":
            while self.demo_timer >= DEMO_GEN_INTERVAL and self.demo_generation < len(frames):
                self.demo_timer -= DEMO_GEN_INTERVAL
                self.demo_generation += 1
            if self.demo_generation == len(frames):
                self.demo_phase, self.demo_timer = "won", 0.0
        elif self.demo_timer >= DEMO_WIN_PAUSE:
            self._restart_demo()

    def exit(self) -> None:
        pass

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if not getattr(input_data, "pressed", False):
            return

        if input_id == "nav_left":
            self._set_page(max(0, self.page - 1))
        elif input_id == "nav_right":
            self._set_page(min(len(PAGES) - 1, self.page + 1))
        elif input_id in ("open_guide", "confirm", "back"):
            self.game.hide_overlay()

    def update(self, dt: float) -> None:
        demo = next((item for item in PAGES[self.page][1] if item[0] == "demo"), None)
        if demo is not None:
            self._update_demo(dt, demo[1])

    # -- Render -------------------------------------------------------------

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(settings.BACKGROUND_COLOR)
        # La guía tapa por completo lo que haya debajo, incluido el texto
        # del menú o del HUD que ya se encoló (ver src/text.py).
        text_layer.discard_queued()

        title, items = PAGES[self.page]
        center_x = settings.VIRTUAL_WIDTH // 2
        render_text(surface, "GUÍA DE JUEGO", settings.FONTS["hud"], center_x, 16, DIM_COLOR, center=True)
        render_text(surface, title, settings.FONTS["banner"], center_x, 40, settings.HUD_ACCENT_COLOR, center=True)
        pygame.draw.line(
            surface, settings.GRID_LINE_COLOR, (MARGIN_X, 58), (settings.VIRTUAL_WIDTH - MARGIN_X, 58)
        )

        y = CONTENT_TOP
        for item in items:
            kind = item[0]
            if kind == "text":
                y = self._render_text_item(surface, item[1], item[2], y)
            elif kind == "key":
                y = self._render_key_item(surface, item[1], item[2], y)
            elif kind == "pattern":
                y = self._render_pattern_item(surface, item[1], item[2], item[3], y)
            elif kind == "swatch":
                y = self._render_swatch_item(surface, item[1], item[2], y)
            elif kind == "demo":
                y = self._render_demo_item(surface, item[1])
            y += ITEM_GAP

        pygame.draw.line(
            surface,
            settings.GRID_LINE_COLOR,
            (MARGIN_X, settings.VIRTUAL_HEIGHT - 34),
            (settings.VIRTUAL_WIDTH - MARGIN_X, settings.VIRTUAL_HEIGHT - 34),
        )
        render_text(
            surface,
            f"< Página {self.page + 1} de {len(PAGES)} >    IZQ/DER: cambiar página    G / ESC: cerrar",
            settings.FONTS["hud"],
            center_x,
            settings.VIRTUAL_HEIGHT - 18,
            DIM_COLOR,
            center=True,
        )

    def _render_body(self, surface: pygame.Surface, body: str, x: int, y: int) -> int:
        font = settings.FONTS["hud"]
        for line in _wrap(body, font, settings.VIRTUAL_WIDTH - MARGIN_X - x):
            render_text(surface, line, font, x, y, settings.HUD_TEXT_COLOR)
            y += LINE_HEIGHT
        return y

    def _render_text_item(self, surface: pygame.Surface, heading: str, body: str, y: int) -> int:
        render_text(surface, heading, settings.FONTS["hud"], MARGIN_X, y, settings.HUD_ACCENT_COLOR)
        return self._render_body(surface, body, MARGIN_X + 10, y + HEADING_HEIGHT)

    def _render_key_item(self, surface: pygame.Surface, key: str, action: str, y: int) -> int:
        render_text(surface, key, settings.FONTS["hud"], MARGIN_X, y, settings.HUD_ACCENT_COLOR)
        return self._render_body(surface, action, MARGIN_X + KEY_COLUMN_WIDTH, y)

    def _render_pattern_item(
        self, surface: pygame.Surface, rows: Sequence[str], name: str, body: str, y: int
    ) -> int:
        size = 3 * PATTERN_CELL
        for row_index, row in enumerate(rows):
            for col_index, char in enumerate(row):
                rect = pygame.Rect(
                    MARGIN_X + col_index * PATTERN_CELL,
                    y + row_index * PATTERN_CELL,
                    PATTERN_CELL,
                    PATTERN_CELL,
                )
                if char == "#":
                    surface.fill(settings.PLAYER_CELL_COLOR, rect)
                pygame.draw.rect(surface, settings.GRID_LINE_COLOR, rect, width=1)

        text_x = MARGIN_X + size + 16
        render_text(surface, name, settings.FONTS["hud"], text_x, y, settings.HUD_ACCENT_COLOR)
        end_y = self._render_body(surface, body, text_x, y + HEADING_HEIGHT)
        return max(end_y, y + len(rows) * PATTERN_CELL) + ITEM_GAP

    def _render_swatch_item(self, surface: pygame.Surface, color: pygame.Color, body: str, y: int) -> int:
        rect = pygame.Rect(MARGIN_X, y + 1, SWATCH_SIZE, SWATCH_SIZE)
        if color == settings.CURSOR_COLOR:
            pygame.draw.rect(surface, color, rect, width=2)
        else:
            surface.fill(color, rect)
        return self._render_body(surface, body, MARGIN_X + SWATCH_SIZE + 10, y)

    def _render_demo_item(self, surface: pygame.Surface, level_index: int) -> int:
        level = LEVELS[level_index]
        placed, frames = DEMOS[level_index]
        if self.demo_generation == 0:
            alive = set(level.enemy_cells) | set(placed[: self.demo_placed])
        else:
            alive = frames[self.demo_generation - 1]

        # Mismo mapa y colores que BoardRenderer, a escala reducida.
        columns, rows = settings.GRID_COLUMNS, settings.GRID_ROWS
        left = (settings.VIRTUAL_WIDTH - columns * DEMO_CELL) // 2
        area = pygame.Rect(left, DEMO_TOP, columns * DEMO_CELL, rows * DEMO_CELL)

        def cell_rect(col: int, row: int) -> pygame.Rect:
            return pygame.Rect(left + col * DEMO_CELL, DEMO_TOP + row * DEMO_CELL, DEMO_CELL, DEMO_CELL)

        for col, row in level.target_zone:
            surface.fill(settings.TARGET_ZONE_COLOR, cell_rect(col, row))
        for col, row in level.walls:
            surface.fill(settings.WALL_COLOR, cell_rect(col, row))
        for col, row in alive:
            color = settings.ENEMY_CELL_COLOR if (col, row) in level.enemy_cells else settings.PLAYER_CELL_COLOR
            surface.fill(color, cell_rect(col, row))
        for col in range(columns + 1):
            x = left + col * DEMO_CELL
            pygame.draw.line(surface, settings.GRID_LINE_COLOR, (x, area.top), (x, area.bottom))
        for row in range(rows + 1):
            y = DEMO_TOP + row * DEMO_CELL
            pygame.draw.line(surface, settings.GRID_LINE_COLOR, (area.left, y), (area.right, y))
        if self.demo_phase == "place" and self.demo_placed < len(placed):
            # Cursor sobre la próxima casilla, como en el juego.
            pygame.draw.rect(surface, settings.CURSOR_COLOR, cell_rect(*placed[self.demo_placed]), width=2)

        if self.demo_phase == "place":
            status = f"Gen: 0   Colocando células con clic ({self.demo_placed}/{len(placed)})"
            status_color = settings.HUD_TEXT_COLOR
        elif self.demo_phase == "ready":
            status = "Gen: 0   Diseño listo: presiona ESPACIO para simular"
            status_color = settings.HUD_ACCENT_COLOR
        elif self.demo_phase == "run":
            status = f"Gen: {self.demo_generation}   SIMULANDO"
            status_color = settings.HUD_ACCENT_COLOR
        else:
            status = f"NIVEL COMPLETADO en la generación {self.demo_generation}"
            status_color = settings.WIN_BANNER_COLOR
        render_text(
            surface, status, settings.FONTS["hud"], settings.VIRTUAL_WIDTH // 2, area.bottom + 11,
            status_color, center=True,
        )

        todo, expected = DEMO_CAPTIONS[level_index]
        y = self._render_text_item(surface, "Qué hacer", todo, area.bottom + 24)
        return self._render_text_item(surface, "Qué deberías ver", expected, y + 2)
