"""
This file contains the class PlayState: the main (and only) playable
screen. It drives Modulo A (src.board.board.Board) for swaps / matches
/ gravity, keeps a running score, and drives Modulo C
(src.combat.combat_manager.CombatManager) for the RPG layer: every
match found by the board triggers its element's combat effect against
the enemy (or the player, for Agua), and once the player's move fully
resolves the enemy gets an automatic turn.
"""

from typing import Optional, Tuple

import pygame

from gale.input_handler import InputData
from gale.state import BaseState
from gale.text import render_text
from gale.timer import Timer

import settings
from src.board.board import Board
from src.combat import Character, CombatManager


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

    # -- Input ------------------------------------------------------------

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if input_id == "click" and input_data.pressed:
            self._on_click(input_data.position)

    def _on_click(self, position: Tuple[int, int]) -> None:
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

    def _process_matches(self, runs) -> None:
        # Cada corrida dispara el efecto de combate de su propio
        # elemento (Modulo C) antes de limpiar el tablero -- así el
        # tamaño real del match (3/4/5+) llega intacto a CombatManager.
        for run in runs:
            self.combat.apply_player_match(run.kind, len(run.tiles))

        _kind_counts, catalysis, cleared_count = self.board.resolve_runs(runs)

        self.combo += 1
        self.score += cleared_count * settings.POINTS_PER_TILE
        if catalysis:
            self.score += settings.CATALYSIS_BONUS

        falling = self.board.get_falling_tiles()
        Timer.tween(0.25, falling, on_finish=self._after_fall)

    def _after_fall(self) -> None:
        runs = self.board.find_matches()

        if runs:
            self._process_matches(runs)
            return

        # La jugada del jugador termino de resolverse por completo:
        # si nadie gano/perdio todavia, le toca el turno automatico
        # al enemigo antes de devolver el control del tablero.
        result = self.combat.check_result()
        if result is not None:
            self.result = result
            return

        self.combat.enemy_turn(on_finish=self._after_enemy_turn)

    def _after_enemy_turn(self) -> None:
        result = self.combat.check_result()
        if result is not None:
            self.result = result
        else:
            self.active = True
