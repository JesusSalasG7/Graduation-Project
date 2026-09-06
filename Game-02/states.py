"""
states.py

Estados de la Máquina de Estados de Gale para 2048:
  - CoverState: pantalla de inicio con la imagen de portada (Cover.png).
  - PlayState: tablero jugable, entrada de flechas, marcador.
  - GameOverState: pantalla final (victoria o derrota) con reinicio.
"""
from __future__ import annotations

import math
import random
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pygame

from gale.state import BaseState

import settings
from logic2048 import GRID_SIZE, TileMovement, Board

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
DIRECTIONS_BY_ACTION = {
    "move_left": "LEFT",
    "move_right": "RIGHT",
    "move_up": "UP",
    "move_down": "DOWN",
}

# ---------------------------------------------------------------------------
# Animación: duración de cada fase de un movimiento, en segundos.
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


def _ease_out_cubic(t: float) -> float:
    """Desaceleración suave al llegar al destino (en vez de movimiento lineal robótico)."""
    return 1.0 - (1.0 - t) ** 3


def _cell_rect(row: float, col: float) -> pygame.Rect:
    """Acepta fila/col fraccionarios: son los que usa la animación de deslizamiento."""
    x = BOARD_LEFT + CELL_GAP + col * (CELL_SIZE + CELL_GAP)
    y = BOARD_TOP + CELL_GAP + row * (CELL_SIZE + CELL_GAP)
    return pygame.Rect(round(x), round(y), CELL_SIZE, CELL_SIZE)


# ---------------------------------------------------------------------------
# Fondo "espacial" (degradado + resplandores + estrellas) y tarjeta central.
#
# Generar esto píxel a píxel sería lento si se hiciera en cada frame, así
# que se arma UNA sola vez (un degradado vertical de ~850 líneas más un
# puñado de círculos para los halos y las estrellas) y se cachea en
# `_BACKGROUND_CACHE`, indexado por tamaño de ventana. `PlayState.enter()` se
# vuelve a llamar cada vez que el jugador reinicia (tecla R), así que sin
# este caché se repetiría el costo de generar el fondo en cada reinicio.
# ---------------------------------------------------------------------------
_BACKGROUND_CACHE: Dict[Tuple[int, int], pygame.Surface] = {}


def _blend_color(color_a: Tuple[int, int, int], color_b: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
    """Interpola linealmente entre dos colores RGB según t en [0, 1]."""
    return tuple(int(color_a[i] + (color_b[i] - color_a[i]) * t) for i in range(3))


def _draw_glow(
    base: pygame.Surface, center: Tuple[int, int], max_radius: float, color: Tuple[int, int, int]
) -> None:
    """
    Simula un halo de luz suave: dibuja muchos círculos concéntricos, cada
    uno casi transparente, sobre una capa auxiliar con canal alfa, y la
    mezcla con el fondo en modo aditivo (suma de color, no reemplazo) para
    que el resultado se vea como un brillo y no como un círculo sólido.
    """
    layers = 24
    overlay = pygame.Surface(base.get_size(), pygame.SRCALPHA)
    for i in range(layers, 0, -1):
        radius = int(max_radius * i / layers)
        alpha = int(2 + (i / layers) * 9)  # muy sutil: capas finas que se van sumando
        pygame.draw.circle(overlay, (*color, alpha), center, radius)
    base.blit(overlay, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)


def _space_background(width: int, height: int) -> pygame.Surface:
    """Devuelve (generándolo una sola vez y reutilizándolo después) el fondo estrellado."""
    key = (width, height)
    if key in _BACKGROUND_CACHE:
        return _BACKGROUND_CACHE[key]

    surface = pygame.Surface((width, height))

    # Degradado vertical azul marino -> púrpura (barato: una línea por fila,
    # no un cálculo por píxel).
    for y in range(height):
        t = y / max(1, height - 1)
        color = _blend_color(COLOR_BACKGROUND_TOP, COLOR_BACKGROUND_BOTTOM, t)
        pygame.draw.line(surface, color, (0, y), (width, y))

    # Halos de color en las esquinas opuestas, para sugerir profundidad
    # diagonal sin tener que calcular un degradado diagonal real.
    _draw_glow(surface, (0, 0), max(width, height) * 0.55, COLOR_GLOW_BLUE)
    _draw_glow(surface, (width, height), max(width, height) * 0.6, COLOR_GLOW_MAGENTA)

    # Estrellas decorativas: semilla fija para que el cielo generado sea
    # siempre el mismo (reproducible), no distinto en cada partida.
    generator = random.Random(20480)
    for _ in range(70):
        x = generator.randint(0, width - 1)
        y = generator.randint(0, height - 1)
        radius = generator.choice((1, 1, 1, 2))
        brightness = generator.randint(90, 200)
        pygame.draw.circle(surface, (brightness, brightness, min(255, brightness + 35)), (x, y), radius)

    _BACKGROUND_CACHE[key] = surface
    return surface


def _draw_panel(surface: pygame.Surface) -> None:
    """Tarjeta oscura con borde brillante que enmarca todo el juego, sobre el fondo estrellado."""
    margin = 14
    radius = 28
    panel_rect = pygame.Rect(margin, margin, WINDOW_WIDTH - 2 * margin, WINDOW_HEIGHT - 2 * margin)

    pygame.draw.rect(surface, COLOR_PANEL, panel_rect, border_radius=radius)

    # Resplandor del borde: tres anillos concéntricos hacia afuera del
    # panel, cada vez más grandes y más tenues (mismo truco que el halo de
    # fondo, pero como simples trazos en vez de círculos rellenos).
    rings = ((2, 1.0), (5, 0.55), (9, 0.3))
    for offset, intensity in rings:
        ring_color = tuple(int(c * intensity) for c in COLOR_PANEL_BORDER)
        border_rect = panel_rect.inflate(offset * 2, offset * 2)
        pygame.draw.rect(surface, ring_color, border_rect, width=2, border_radius=radius + offset)


def _draw_text_with_glow(
    surface: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    main_color: Tuple[int, int, int],
    glow_color: Tuple[int, int, int],
    corner_position: Tuple[int, int],
) -> None:
    """
    Efecto de "glow" barato: primero se dibuja el mismo texto en un color
    cálido varias veces, desplazado un par de píxeles en las 8 direcciones
    alrededor de la posición final, formando un halo/contorno grueso; luego
    se dibuja el texto real, en el color principal, exactamente encima.
    """
    glow_text = font.render(text, True, glow_color)
    for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, 2), (-2, 2), (2, -2)):
        surface.blit(glow_text, (corner_position[0] + dx, corner_position[1] + dy))

    main_text = font.render(text, True, main_color)
    surface.blit(main_text, corner_position)


# ---------------------------------------------------------------------------
# Portada (Cover.png): se carga y se reescala una sola vez -igual que el
# fondo estrellado- y se cachea por tamaño de ventana, para no tocar disco
# ni reescalar de nuevo si el jugador vuelve a ver la portada.
# ---------------------------------------------------------------------------
_COVER_PATH = Path(__file__).resolve().parent / "assets" / "Cover.png"
_COVER_CACHE: Dict[Tuple[int, int], Tuple[pygame.Surface, pygame.Rect]] = {}


def _cover_image(window_width: int, window_height: int) -> Tuple[pygame.Surface, pygame.Rect]:
    key = (window_width, window_height)
    if key in _COVER_CACHE:
        return _COVER_CACHE[key]

    original = pygame.image.load(str(_COVER_PATH)).convert_alpha()

    # Se escala preservando la proporción original, para que quepa entera
    # dentro de la ventana sin deformarse (el lado que sobre queda como
    # margen, centrado).
    scale = min(window_width / original.get_width(), window_height / original.get_height())
    new_width = round(original.get_width() * scale)
    new_height = round(original.get_height() * scale)
    image = pygame.transform.smoothscale(original, (new_width, new_height))
    rect = image.get_rect(center=(window_width // 2, window_height // 2))

    _COVER_CACHE[key] = (image, rect)
    return _COVER_CACHE[key]


# ---------------------------------------------------------------------------
# Audio (assets/check.mp3): se reproduce al fusionar dos fichas y al
# confirmar en la portada. Se carga una sola vez (cacheado) igual que la
# imagen de portada y el fondo.
# ---------------------------------------------------------------------------
_CHECK_SOUND_PATH = Path(__file__).resolve().parent / "assets" / "check.mp3"
_SOUND_CACHE: Dict[str, Optional[pygame.mixer.Sound]] = {}


def _check_sound() -> Optional[pygame.mixer.Sound]:
    """
    Carga (una sola vez) el efecto 'check'. Si el mezclador de audio no
    está disponible en el entorno actual (por ejemplo, sin dispositivo de
    sonido en un servidor sin cabeza), se atrapa el error y se devuelve
    None: el juego sigue funcionando en silencio en vez de fallar.
    """
    if "check" not in _SOUND_CACHE:
        try:
            _SOUND_CACHE["check"] = pygame.mixer.Sound(str(_CHECK_SOUND_PATH))
        except pygame.error:
            _SOUND_CACHE["check"] = None

    return _SOUND_CACHE["check"]


# ---------------------------------------------------------------------------
# Música de fondo (assets/Bucle_music.mp3): suena en bucle infinito durante
# la partida. A diferencia de check.mp3 (un efecto corto que se carga
# entero en memoria con pygame.mixer.Sound), esta es una pista larga
# pensada para sonar de fondo, así que se transmite con pygame.mixer.music
# -sólo puede haber una activa a la vez, que es justo lo que se necesita
# para música de fondo- en vez de cargarla completa en RAM.
# ---------------------------------------------------------------------------
_GAME_MUSIC_PATH = Path(__file__).resolve().parent / "assets" / "Bucle_music.mp3"


def _start_game_music() -> None:
    """
    Carga y reproduce Bucle_music.mp3 en bucle infinito (loops=-1). Se
    llama cada vez que arranca una partida (PlayState.enter), incluido un
    reinicio, así que la música también vuelve a empezar desde el inicio
    en cada reinicio. Si no hay dispositivo de audio disponible, se
    atrapa el error y la partida sigue en silencio.
    """
    try:
        pygame.mixer.music.load(str(_GAME_MUSIC_PATH))
        pygame.mixer.music.play(loops=-1)
    except pygame.error:
        pass


def _stop_music() -> None:
    """Corta la música de fondo (se llama al salir de PlayState: game over)."""
    try:
        pygame.mixer.music.stop()
    except pygame.error:
        pass


class CoverState(BaseState):
    """
    Pantalla de inicio: muestra Cover.png sobre el fondo espacial, con un
    mensaje parpadeante, hasta que el jugador presiona ENTER (ESC sigue
    saliendo del juego: Game2048.on_input la intercepta antes de que
    llegue aquí). Es el primer estado que ve el jugador al arrancar.
    """

    PROMPT_BAR_HEIGHT = 74

    def enter(self, *args, **kwargs) -> None:
        self.prompt_font = pygame.font.SysFont("arial", 24, bold=True)
        self.time = 0.0
        self.image, self.image_rect = _cover_image(WINDOW_WIDTH, WINDOW_HEIGHT)

    def exit(self) -> None:
        pass

    def on_input(self, input_id: str, input_data) -> None:
        # Sólo ENTER (main.py la registra como "confirm", tanto la tecla
        # principal como la del teclado numérico) arranca la partida; se
        # ignora cualquier otra tecla, incluidas las flechas.
        if input_id == "confirm" and getattr(input_data, "pressed", False):
            sound = _check_sound()
            if sound is not None:
                sound.play()
            self.state_machine.change("play")

    def update(self, dt: float) -> None:
        self.time += dt

    def render(self, surface: pygame.Surface) -> None:
        surface.blit(_space_background(*surface.get_size()), (0, 0))
        surface.blit(self.image, self.image_rect)

        # Barra semitransparente en la base, para que el texto se lea sin
        # importar qué haya justo debajo en la imagen de portada.
        bar = pygame.Surface((WINDOW_WIDTH, self.PROMPT_BAR_HEIGHT), pygame.SRCALPHA)
        bar.fill((0, 0, 0, 150))
        surface.blit(bar, (0, WINDOW_HEIGHT - self.PROMPT_BAR_HEIGHT))

        # Parpadeo suave (oscilación seno) en vez de fijo, para que llame
        # la atención como una invitación a jugar.
        alpha = int(160 + 95 * math.sin(self.time * 3.0))
        text = self.prompt_font.render(
            "PRESIONA ENTER PARA JUGAR", True, COLOR_TEXT_PRIMARY
        )
        text.set_alpha(max(0, min(255, alpha)))
        text_rect = text.get_rect(
            center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT - self.PROMPT_BAR_HEIGHT // 2)
        )
        surface.blit(text, text_rect)


class PlayState(BaseState):
    """
    Estado jugable: tablero 4x4, entrada de flechas y marcador.

    La animación de un movimiento avanza por tres fases guardadas en
    `self.phase`:
      "idle"      -> esperando entrada del jugador.
      "sliding"   -> las fichas viajan de origen a destino.
      "appearing" -> ya se ven los valores finales; fusiones y ficha
                     nueva hacen un pequeño "pop" de escala.
    `Board.move()` sigue siendo instantáneo (el tablero lógico queda
    resuelto de inmediato); lo único que se retrasa visualmente es el
    dibujo, interpolando entre la posición anterior y la nueva.
    """

    def enter(self, *args, **kwargs) -> None:
        self.board = Board()

        self.title_font = pygame.font.SysFont("arial", 48, bold=True)
        self.score_font = pygame.font.SysFont("arial", 28, bold=True)
        self.tile_font_large = pygame.font.SysFont("arial", 56, bold=True)
        self.tile_font_medium = pygame.font.SysFont("arial", 45, bold=True)
        self.tile_font_small = pygame.font.SysFont("arial", 34, bold=True)

        self.board_rect = pygame.Rect(BOARD_LEFT, BOARD_TOP, BOARD_PIXEL_SIZE, BOARD_PIXEL_SIZE)

        # Estado de la animación en curso (ver docstring de la clase).
        self.phase: str = "idle"
        self.phase_time: float = 0.0
        self.current_movements: list[TileMovement] = []
        self.merged_cells: Set[Tuple[int, int]] = set()
        self.new_tile_position: Tuple[int, int] | None = None

        # La música de la partida arranca aquí; también se reinicia desde
        # cero cada vez que "restart" vuelve a llamar a este mismo
        # enter() (ver on_input más abajo).
        _start_game_music()

    def exit(self) -> None:
        _stop_music()

    # ------------------------------------------------------------------
    def _font_for(self, value: int) -> pygame.font.Font:
        digits = len(str(value))
        if digits <= 2:
            return self.tile_font_large
        if digits == 3:
            return self.tile_font_medium
        return self.tile_font_small

    # ------------------------------------------------------------------
    # Entrada
    # ------------------------------------------------------------------
    def on_input(self, input_id: str, input_data) -> None:
        if not getattr(input_data, "pressed", False):
            return

        if input_id == "restart":
            self.enter()
            return

        if self.phase != "idle":
            # Se ignoran movimientos nuevos mientras el anterior todavía
            # se está animando, para no encimar deslizamientos.
            return

        direction = DIRECTIONS_BY_ACTION.get(input_id)
        if direction is None:
            return

        result = self.board.move(direction)
        if not result.changed:
            return

        self.current_movements = result.movements
        self.new_tile_position = result.new_tile_position
        self.merged_cells = {m.target for m in result.movements if m.merged}

        self.phase = "sliding"
        self.phase_time = 0.0

    # ------------------------------------------------------------------
    # Actualización de la animación
    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        if self.phase == "idle":
            return

        self.phase_time += dt

        if self.phase == "sliding" and self.phase_time >= SLIDE_DURATION:
            # El deslizamiento terminó: a partir de ahora se dibuja
            # directamente desde self.board.cells (que ya tiene los
            # valores finales, incluida la ficha nueva) con el "pop".
            self.phase = "appearing"
            self.phase_time = 0.0

            # Sonido de fusión: una reproducción por cada par de fichas que
            # se unió en este movimiento (merged_cells trae un
            # elemento por cada celda destino donde convergieron dos
            # fichas), justo cuando el deslizamiento termina y el "pop" de
            # la fusión empieza a verse.
            if self.merged_cells:
                sound = _check_sound()
                if sound is not None:
                    for _ in self.merged_cells:
                        sound.play()

        elif self.phase == "appearing" and self.phase_time >= APPEAR_DURATION:
            self.phase = "idle"
            self.phase_time = 0.0
            if self.board.won or self.board.lost:
                self.state_machine.change(
                    "gameover", won=self.board.won, score=self.board.score
                )

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------
    def render(self, surface: pygame.Surface) -> None:
        surface.blit(_space_background(*surface.get_size()), (0, 0))
        _draw_panel(surface)
        self._draw_header(surface)

        pygame.draw.rect(surface, COLOR_BOARD, self.board_rect, border_radius=8)
        self._draw_empty_cells(surface)

        if self.phase == "sliding":
            self._draw_sliding_tiles(surface)
        else:
            self._draw_static_tiles(surface)

    def _draw_header(self, surface: pygame.Surface) -> None:
        _draw_text_with_glow(
            surface, self.title_font, "2048", COLOR_TEXT_PRIMARY, COLOR_TITLE_GLOW, (30, 18)
        )

        score_text = self.score_font.render(
            f"Puntuación: {self.board.score}", True, COLOR_TEXT_PRIMARY
        )
        score_rect = score_text.get_rect(topright=(WINDOW_WIDTH - 30, 28))
        surface.blit(score_text, score_rect)

        help_text = pygame.font.SysFont("arial", 20).render(
            "Flechas: mover   R: reiniciar   ESC: salir", True, COLOR_TEXT_MUTED
        )
        surface.blit(help_text, (30, 84))

    def _draw_empty_cells(self, surface: pygame.Surface) -> None:
        """Fondo fijo de las 16 celdas, siempre visible debajo de las fichas animadas."""
        for row in range(GRID_SIZE):
            for col in range(GRID_SIZE):
                pygame.draw.rect(surface, TILE_COLORS[0], _cell_rect(row, col), border_radius=6)

    def _draw_tile_in_rect(
        self, surface: pygame.Surface, rect: pygame.Rect, value: int, scale: float = 1.0
    ) -> None:
        color = TILE_COLORS.get(value, COLOR_TILE_EXTRA)

        if scale < 1.0:
            width = max(1, int(rect.width * scale))
            height = max(1, int(rect.height * scale))
            draw_rect = pygame.Rect(0, 0, width, height)
            draw_rect.center = rect.center
        else:
            draw_rect = rect

        pygame.draw.rect(surface, color, draw_rect, border_radius=6)

        text_color = COLOR_TEXT_DARK if value <= 4 else COLOR_TEXT_LIGHT
        font = self._font_for(value)
        text = font.render(str(value), True, text_color)
        surface.blit(text, text.get_rect(center=draw_rect.center))

    def _draw_sliding_tiles(self, surface: pygame.Surface) -> None:
        """
        Fase 1: interpola cada TileMovement entre su celda de origen y
        su celda de destino. Las fichas que se fusionan se dibujan al
        final (por encima) para que se vea con claridad cómo dos fichas
        del mismo valor convergen en una sola celda.
        """
        progress = min(1.0, self.phase_time / SLIDE_DURATION)
        smooth_progress = _ease_out_cubic(progress)

        ordered = sorted(self.current_movements, key=lambda m: m.merged)
        for movement in ordered:
            source_row, source_col = movement.source
            target_row, target_col = movement.target

            row = source_row + (target_row - source_row) * smooth_progress
            col = source_col + (target_col - source_col) * smooth_progress

            self._draw_tile_in_rect(surface, _cell_rect(row, col), movement.source_value)

    def _draw_static_tiles(self, surface: pygame.Surface) -> None:
        """
        Fase 2 ("appearing") y estado "idle": dibuja directamente
        desde el tablero lógico (ya resuelto). Durante "appearing",
        las celdas de fusión y la ficha nueva crecen desde una escala
        menor hasta 1.0 para que su llegada se note.
        """
        pop_progress = 1.0
        if self.phase == "appearing":
            pop_progress = min(1.0, self.phase_time / APPEAR_DURATION)

        for row in range(GRID_SIZE):
            for col in range(GRID_SIZE):
                value = self.board.cells[row][col]
                if value == 0:
                    continue

                scale = 1.0
                if self.phase == "appearing":
                    if (row, col) in self.merged_cells:
                        scale = 0.7 + 0.3 * pop_progress
                    elif self.new_tile_position == (row, col):
                        scale = pop_progress

                self._draw_tile_in_rect(surface, _cell_rect(row, col), value, scale=scale)


class GameOverState(BaseState):
    """Pantalla final: victoria (2048 alcanzado) o derrota (sin movimientos)."""

    def enter(self, won: bool = False, score: int = 0, **kwargs) -> None:
        self.won = won
        self.score = score

        self.title_font = pygame.font.SysFont("arial", 62, bold=True)
        self.text_font = pygame.font.SysFont("arial", 30)
        self.help_font = pygame.font.SysFont("arial", 22)

    def exit(self) -> None:
        pass

    def on_input(self, input_id: str, input_data) -> None:
        if input_id == "restart" and getattr(input_data, "pressed", False):
            self.state_machine.change("play")

    def update(self, dt: float) -> None:
        pass

    def render(self, surface: pygame.Surface) -> None:
        surface.blit(_space_background(*surface.get_size()), (0, 0))
        _draw_panel(surface)

        title_color = COLOR_WIN if self.won else COLOR_LOSE
        title_text = "¡GANASTE!" if self.won else "GAME OVER"
        title = self.title_font.render(title_text, True, title_color)
        title_rect = title.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 80))

        _draw_text_with_glow(
            surface, self.title_font, title_text, title_color, COLOR_TITLE_GLOW, title_rect.topleft
        )

        score_text = self.text_font.render(
            f"Puntuación final: {self.score}", True, COLOR_TEXT_PRIMARY
        )
        score_rect = score_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2))
        surface.blit(score_text, score_rect)

        help_text = self.help_font.render(
            "Presiona R para reiniciar   |   ESC para salir", True, COLOR_TEXT_MUTED
        )
        help_rect = help_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 65))
        surface.blit(help_text, help_rect)
