"""
play_state.py

Tablero jugable: entrada de flechas, animación de movimientos y marcador.
"""
from __future__ import annotations

from typing import Set, Tuple

import pygame
from gale.state import BaseState

from src.audio import check_sound, start_game_music, stop_music
from src.logic2048 import GRID_SIZE, Board, TileMovement
from src.rendering.drawing import cell_rect, draw_panel, draw_text_with_glow, ease_out_cubic, space_background
from src.rendering.theme import (
    APPEAR_DURATION,
    BOARD_LEFT,
    BOARD_PIXEL_SIZE,
    BOARD_TOP,
    COLOR_BOARD,
    COLOR_TEXT_DARK,
    COLOR_TEXT_LIGHT,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    COLOR_TILE_EXTRA,
    COLOR_TITLE_GLOW,
    SLIDE_DURATION,
    TILE_COLORS,
    WINDOW_WIDTH,
)

DIRECTIONS_BY_ACTION = {
    "move_left": "LEFT",
    "move_right": "RIGHT",
    "move_up": "UP",
    "move_down": "DOWN",
}

# ---------------------------------------------------------------------------
# Animación: duración de cada fase de un movimiento, en segundos.


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
        start_game_music()

    def exit(self) -> None:
        stop_music()

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
                sound = check_sound()
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
        surface.blit(space_background(*surface.get_size()), (0, 0))
        draw_panel(surface)
        self._draw_header(surface)

        pygame.draw.rect(surface, COLOR_BOARD, self.board_rect, border_radius=8)
        self._draw_empty_cells(surface)

        if self.phase == "sliding":
            self._draw_sliding_tiles(surface)
        else:
            self._draw_static_tiles(surface)

    def _draw_header(self, surface: pygame.Surface) -> None:
        draw_text_with_glow(
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
                pygame.draw.rect(surface, TILE_COLORS[0], cell_rect(row, col), border_radius=6)

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
        smooth_progress = ease_out_cubic(progress)

        ordered = sorted(self.current_movements, key=lambda m: m.merged)
        for movement in ordered:
            source_row, source_col = movement.source
            target_row, target_col = movement.target

            row = source_row + (target_row - source_row) * smooth_progress
            col = source_col + (target_col - source_col) * smooth_progress

            self._draw_tile_in_rect(surface, cell_rect(row, col), movement.source_value)

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

                self._draw_tile_in_rect(surface, cell_rect(row, col), value, scale=scale)
