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

HINT_DELAY = 4.0


class PlayState(BaseState):
    def enter(self, **_enter_params) -> None:
        self.board = Board(settings.BOARD_X, settings.BOARD_Y)
        self.score = 0
        self.selected: Optional[Tuple[int, int]] = None
        self.active = True
        self.combo = 0

        self.player = Character("Jugador", 100, settings.PLAYER_ANCHOR, is_player=True)
        self.enemy = Character("Enemigo", 100, settings.ENEMY_ANCHOR, is_player=False)
        self.combat = CombatManager(self.player, self.enemy)
        self.result: Optional[str] = None
        self.shuffle_message = False

        self.hint_cells: Optional[Tuple[Tuple[int, int], Tuple[int, int]]] = None
        self._hint_timer = None
        self._restart_hint_timer()

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

        render_text(
            surface,
            f"Puntaje: {self.score}",
            settings.FONTS["small"],
            settings.VIRTUAL_WIDTH // 2,
            settings.TOP_BAR_ZONE.height // 2,
            (235, 235, 240),
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

    def _render_result_overlay(self, surface: pygame.Surface) -> None:
        overlay = pygame.Surface((settings.VIRTUAL_WIDTH, settings.VIRTUAL_HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 8, 16, 190))
        surface.blit(overlay, (0, 0))

        text = "¡VICTORIA!" if self.result == "victoria" else "DERROTA..."
        color = (99, 255, 155) if self.result == "victoria" else (235, 90, 90)
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

    def _on_click(self, position: Tuple[int, int]) -> None:
        self._restart_hint_timer()

        pos_x = position[0] * settings.VIRTUAL_WIDTH // settings.WINDOW_WIDTH
        pos_y = position[1] * settings.VIRTUAL_HEIGHT // settings.WINDOW_HEIGHT

        if (
            self.result is not None
            or not self.active
            or not settings.BOARD_ZONE.collidepoint(pos_x, pos_y)
        ):
            return

        j = (pos_x - self.board.x) // settings.TILE_SIZE
        i = (pos_y - self.board.y) // settings.TILE_SIZE

        if 0 <= i < settings.BOARD_HEIGHT and 0 <= j < settings.BOARD_WIDTH:
            self._handle_board_click(i, j)

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

        _kind_counts, catalysis, cleared_count, diversity_kinds = self.board.resolve_runs(runs)

        self.combo += 1
        self.score += cleared_count * settings.POINTS_PER_TILE
        if catalysis:
            self.score += settings.CATALYSIS_BONUS
            # Desafio A05 (src/algorithm.py): bonus extra por cada
            # elemento distinto que arrastro la Catalisis.
            self.score += diversity_kinds * settings.DIVERSITY_BONUS_PER_KIND

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
            self.result = result
            return

        self.combat.enemy_turn(on_finish=self._after_enemy_turn)

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
            self.result = result
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
