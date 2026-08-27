"""
This file contains the class PlayState: the main (and only) playable
screen. It drives Modulo A (src.board.board.Board) for swaps / matches
/ gravity, keeps a running score, and drives Modulo C
(src.combat.combat_manager.CombatManager) for the RPG layer: every
match found by the board triggers its element's combat effect against
the enemy (or the player, for Agua), and once the player's move fully
resolves the enemy gets an automatic turn.

It also runs a hint timer: some valid swaps produce a match nowhere
near the two tiles moved (see Board.find_hint), so a board can look
stuck even when it isn't. If the player goes HINT_DELAY seconds
without clicking while it's their turn, the two tiles of a legal move
get a pulsing highlight.
"""

import math

from typing import Optional, Tuple

import pygame

from gale.input_handler import InputData
from gale.state import BaseState
from gale.text import render_text
from gale.timer import Timer

import settings
from src.board.board import Board
from src.combat import Character, CombatManager

HINT_DELAY = 5.0

# Cuanto dura en pantalla el aviso de bonus de Resonancia Elemental
# (ver _show_resonance_message) antes de desvanecerse solo.
RESONANCE_MESSAGE_DURATION = 1.5

# Botones de la pantalla de fin de partida (ver _render_result_overlay
# / _handle_result_click): opcion 0 reinicia la partida, opcion 1 sale
# del juego.
RESULT_OPTIONS = ("Volver a jugar", "Salir")
RESULT_BUTTON_SIZE = (200, 44)
RESULT_BUTTON_GAP = 16


class PlayState(BaseState):
    def enter(self, **_enter_params) -> None:
        self.board = Board(settings.BOARD_X, settings.BOARD_Y)
        self.score = 0
        self.selected: Optional[Tuple[int, int]] = None
        self.active = True
        self.combo = 0

        self.player = Character("Jugador", settings.PLAYER_MAX_HP, settings.PLAYER_ANCHOR, is_player=True)
        self.enemy = Character("Enemigo", settings.ENEMY_MAX_HP, settings.ENEMY_ANCHOR, is_player=False)
        self.combat = CombatManager(self.player, self.enemy)
        self.result: Optional[str] = None
        self.time_up = False
        self.result_selected = 0
        self.result_button_rects = [None, None]
        self.shuffle_message = False
        self.resonance_message: Optional[str] = None

        self.time_remaining = float(settings.COMBAT_TIME_LIMIT)

        self.hint_cells: Optional[Tuple[Tuple[int, int], Tuple[int, int]]] = None
        self._hint_timer = None
        self._restart_hint_timer()

    # -- Tiempo ---------------------------------------------------------

    def update(self, dt: float) -> None:
        if self.result is not None:
            return

        # Corre en tiempo real -- no se pausa mientras el tablero
        # anima o le toca al enemigo -- para que el jugador sienta la
        # presion del reloj tambien mientras decide su proxima jugada.
        self.time_remaining = max(0.0, self.time_remaining - dt)
        if self.time_remaining <= 0:
            self._set_result("derrota", time_up=True)

    def _set_result(self, result: str, time_up: bool = False) -> None:
        self.result = result
        self.time_up = time_up
        self.result_selected = 0
        self.active = False

    # -- Render -------------------------------------------------------

    def render(self, surface: pygame.Surface) -> None:
        self.board.render(surface)
        self.combat.render(surface)

        if self.selected is not None:
            i, j = self.selected
            rect = pygame.Rect(
                self.board.x + j * settings.TILE_SIZE,
                self.board.y + i * settings.TILE_SIZE,
                settings.TILE_SIZE,
                settings.TILE_SIZE,
            )
            pygame.draw.rect(surface, (255, 255, 255), rect, width=3, border_radius=6)

        if self.hint_cells is not None:
            self._render_hint(surface)

        self._render_timer(surface)

        if self.resonance_message:
            render_text(
                surface,
                self.resonance_message,
                settings.FONTS["small"],
                settings.VIRTUAL_WIDTH // 2,
                settings.BOARD_Y + 24,
                (255, 210, 80),
                center=True,
                shadowed=True,
            )

        if self.shuffle_message:
            render_text(
                surface,
                "¡Sin movimientos! Barajando...",
                settings.FONTS["small"],
                settings.VIRTUAL_WIDTH // 2,
                settings.BOARD_Y + settings.BOARD_PIXEL_HEIGHT // 2,
                (235, 235, 240),
                center=True,
                shadowed=True,
            )

        if self.result is not None:
            self._render_result_overlay(surface)

    def _render_timer(self, surface: pygame.Surface) -> None:
        seconds = math.ceil(self.time_remaining)
        text = f"{seconds // 60:01d}:{seconds % 60:02d}"
        # Mismo umbral que HP_BAR "rojo" (ver Character._render_hp_bar):
        # avisa cuando queda poco tiempo, no solo poca vida.
        color = (220, 70, 70) if self.time_remaining <= 10 else (235, 235, 240)
        render_text(
            surface,
            text,
            settings.FONTS["small"],
            settings.VIRTUAL_WIDTH - 40,
            settings.TOP_BAR_ZONE.height // 2,
            color,
            center=True,
            shadowed=True,
        )

    def _render_result_overlay(self, surface: pygame.Surface) -> None:
        overlay = pygame.Surface((settings.VIRTUAL_WIDTH, settings.VIRTUAL_HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 8, 16, 190))
        surface.blit(overlay, (0, 0))

        if self.result == "derrota" and self.time_up:
            render_text(
                surface,
                "Se acabo el tiempo",
                settings.FONTS["small"],
                settings.VIRTUAL_WIDTH // 2,
                settings.VIRTUAL_HEIGHT // 2 - 90,
                (235, 235, 240),
                center=True,
                shadowed=True,
            )

        text, color = ("¡VICTORIA!", (99, 255, 155)) if self.result == "victoria" else ("DERROTA...", (235, 90, 90))
        render_text(
            surface,
            text,
            settings.FONTS["huge"],
            settings.VIRTUAL_WIDTH // 2,
            settings.VIRTUAL_HEIGHT // 2,
            color,
            center=True,
            shadowed=True,
        )

        render_text(
            surface,
            f"Puntaje final: {self.score}",
            settings.FONTS["small"],
            settings.VIRTUAL_WIDTH // 2,
            settings.VIRTUAL_HEIGHT // 2 + 55,
            (235, 235, 240),
            center=True,
            shadowed=True,
        )

        self._render_result_buttons(surface)

    def _render_result_buttons(self, surface: pygame.Surface) -> None:
        width, height = RESULT_BUTTON_SIZE
        first_y = settings.VIRTUAL_HEIGHT // 2 + 95

        for index, label in enumerate(RESULT_OPTIONS):
            rect = pygame.Rect(0, 0, width, height)
            rect.center = (
                settings.VIRTUAL_WIDTH // 2,
                first_y + index * (height + RESULT_BUTTON_GAP),
            )
            self.result_button_rects[index] = rect

            selected = index == self.result_selected
            border_color = (255, 210, 80) if selected else (150, 145, 160)
            pygame.draw.rect(surface, (30, 24, 40), rect, border_radius=8)
            pygame.draw.rect(surface, border_color, rect, width=3, border_radius=8)

            render_text(
                surface,
                label,
                settings.FONTS["small"],
                rect.centerx,
                rect.centery,
                (235, 235, 240),
                center=True,
                shadowed=True,
            )

    def _render_hint(self, surface: pygame.Surface) -> None:
        # A soft pulse (no Timer needed -- just riding the clock) so
        # it reads as a suggestion, not another selection outline.
        pulse = (math.sin(pygame.time.get_ticks() / 200) + 1) / 2
        alpha = round(120 + 100 * pulse)
        highlight = pygame.Surface((settings.TILE_SIZE, settings.TILE_SIZE), pygame.SRCALPHA)
        pygame.draw.rect(
            highlight,
            (255, 210, 80, alpha),
            highlight.get_rect(),
            width=3,
            border_radius=6,
        )
        for i, j in self.hint_cells:
            surface.blit(
                highlight,
                (self.board.x + j * settings.TILE_SIZE, self.board.y + i * settings.TILE_SIZE),
            )

    # -- Input ------------------------------------------------------------

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if input_id == "click" and input_data.pressed:
            self._on_click(input_data.position)
            return

        if self.result is None or not input_data.pressed:
            return

        if input_id in ("up", "down"):
            self.result_selected = 1 - self.result_selected
        elif input_id == "enter":
            self._activate_result_option(self.result_selected)

    def _on_click(self, position: Tuple[int, int]) -> None:
        pos_x = position[0] * settings.VIRTUAL_WIDTH // settings.WINDOW_WIDTH
        pos_y = position[1] * settings.VIRTUAL_HEIGHT // settings.WINDOW_HEIGHT

        if self.result is not None:
            self._handle_result_click(pos_x, pos_y)
            return

        self._restart_hint_timer()

        if not self.active or not settings.BOARD_ZONE.collidepoint(pos_x, pos_y):
            return

        j = (pos_x - self.board.x) // settings.TILE_SIZE
        i = (pos_y - self.board.y) // settings.TILE_SIZE

        if 0 <= i < settings.BOARD_HEIGHT and 0 <= j < settings.BOARD_WIDTH:
            self._handle_board_click(i, j)

    # -- Fin de partida: volver a jugar / salir ------------------------

    def _handle_result_click(self, pos_x: int, pos_y: int) -> None:
        for index, rect in enumerate(self.result_button_rects):
            if rect is not None and rect.collidepoint(pos_x, pos_y):
                self._activate_result_option(index)
                return

    def _activate_result_option(self, index: int) -> None:
        if index == 0:
            self.state_machine.change("play")
        else:
            pygame.event.post(pygame.event.Event(pygame.QUIT))

    def _handle_board_click(self, i: int, j: int) -> None:
        if self.selected is None:
            self.selected = (i, j)
            return

        i1, j1 = self.selected

        if (i1, j1) == (i, j):
            self.selected = None
            return

        di, dj = abs(i - i1), abs(j - j1)

        if (di == 1 and dj == 0) or (di == 0 and dj == 1):
            self.selected = None
            self._attempt_swap(i1, j1, i, j)
        else:
            self.selected = (i, j)

    # -- Swap / match / gravity cascade ------------------------------------

    def _swap_matrix(self, tile1, tile2) -> None:
        board = self.board
        board.tiles[tile1.i][tile1.j], board.tiles[tile2.i][tile2.j] = (
            board.tiles[tile2.i][tile2.j],
            board.tiles[tile1.i][tile1.j],
        )
        tile1.i, tile1.j, tile2.i, tile2.j = tile2.i, tile2.j, tile1.i, tile1.j

    def _attempt_swap(self, i1: int, j1: int, i2: int, j2: int) -> None:
        self.active = False
        tile1 = self.board.tiles[i1][j1]
        tile2 = self.board.tiles[i2][j2]

        def arrive():
            self._swap_matrix(tile1, tile2)
            runs = self.board.find_matches()

            if not runs:
                Timer.tween(
                    0.2,
                    [
                        (tile1, {"x": tile2.x, "y": tile2.y}),
                        (tile2, {"x": tile1.x, "y": tile1.y}),
                    ],
                    on_finish=lambda: self._finish_revert(tile1, tile2),
                )
                return

            self.combo = 0
            self._process_matches(runs)

        Timer.tween(
            0.2,
            [(tile1, {"x": tile2.x, "y": tile2.y}), (tile2, {"x": tile1.x, "y": tile1.y})],
            on_finish=arrive,
        )

    def _finish_revert(self, tile1, tile2) -> None:
        self._swap_matrix(tile1, tile2)
        self.active = True
        self._restart_hint_timer()

    def _process_matches(self, runs) -> None:
        # Cada corrida dispara el efecto de combate de su propio
        # elemento (Modulo C) antes de limpiar el tablero -- así el
        # tamaño real del match (3/4/5+) llega intacto a CombatManager.
        for run in runs:
            self.combat.apply_player_match(run.kind, len(run.tiles))

        _kind_counts, catalysis, cleared_count, resonance_kinds = self.board.resolve_runs(runs)

        self.combo += 1
        self.score += cleared_count * settings.POINTS_PER_TILE
        if catalysis:
            self.score += settings.CATALYSIS_BONUS
            # Desafio A05 (src/algorithm.py): bonus extra por cada
            # elemento que se repitio dentro de la linea que arrastro
            # la Catalisis.
            resonance_bonus = resonance_kinds * settings.RESONANCE_BONUS_PER_KIND
            self.score += resonance_bonus
            if resonance_bonus:
                self._show_resonance_message(resonance_kinds, resonance_bonus)

        falling = self.board.get_falling_tiles()
        Timer.tween(0.25, falling, on_finish=self._after_fall)

    def _after_fall(self) -> None:
        runs = self.board.find_matches()

        if runs:
            self._process_matches(runs)
            return

        self._reshuffle_if_stuck()

        # La jugada del jugador termino de resolverse por completo:
        # si nadie gano/perdio todavia, le toca el turno automatico
        # al enemigo antes de devolver el control del tablero.
        result = self.combat.check_result()
        if result is not None:
            self._set_result(result)
            return

        self.combat.enemy_turn(on_finish=self._after_enemy_turn)

    def _show_resonance_message(self, resonance_kinds: int, resonance_bonus: int) -> None:
        # Desafio A05 (src/algorithm.py): hace visible en pantalla lo
        # que find_repeated calculo -- cuantos elementos se repitieron
        # dentro de la linea que arrastro la Catalisis y cuanto pago
        # ese bonus de Resonancia Elemental, que de otro modo quedaria
        # invisible dentro de self.score.
        self.resonance_message = f"¡Resonancia x{resonance_kinds}! +{resonance_bonus}"
        Timer.after(RESONANCE_MESSAGE_DURATION, lambda: setattr(self, "resonance_message", None))

    def _reshuffle_if_stuck(self) -> None:
        # Una cascada puede asentarse en un tablero sin ninguna jugada
        # legal (ver Board.has_possible_moves) -- rebarajarlo ahi mismo
        # en vez de dejar al jugador sin poder hacer nada.
        if self.board.has_possible_moves():
            return

        self.board.shuffle()
        self.shuffle_message = True
        Timer.after(1.2, lambda: setattr(self, "shuffle_message", False))

    def _after_enemy_turn(self) -> None:
        result = self.combat.check_result()
        if result is not None:
            self._set_result(result)
        else:
            self.active = True
            self._restart_hint_timer()

    # -- Hints --------------------------------------------------------------

    def _restart_hint_timer(self) -> None:
        self.hint_cells = None
        if self._hint_timer is not None:
            self._hint_timer.remove()
        self._hint_timer = Timer.after(HINT_DELAY, self._show_hint)

    def _show_hint(self) -> None:
        if not self.active or self.result is not None:
            return
        self.hint_cells = self.board.find_hint()
