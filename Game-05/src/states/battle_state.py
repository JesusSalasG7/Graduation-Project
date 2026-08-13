"""
This file contains the class BattleState: the main playable screen.
It owns no combat rules or board rules of its own -- it drives Modulo
A (src.board.board.Board) for swaps/matches/gravity and Modulo C
(src.combat.combat_controller.CombatController) for what those matches
mean in HP/essence terms, and renders both plus the HUD
(src.ui.hud) split across settings.COMBAT_ZONE / BOARD_ZONE /
POWER_BAR_ZONE.
"""

from typing import Any, Dict, Optional, Tuple

import pygame

from gale.input_handler import InputData
from gale.state import BaseState
from gale.text import render_text
from gale.timer import Timer

import settings
from src.combat.enemies import ENEMY_COUNT
from src.rpg.powers import POWERS
from src.ui import hud


class BattleState(BaseState):
    def enter(self, **enter_params: Dict[str, Any]) -> None:
        self.level = enter_params["level"]
        self.board = enter_params["board"]
        self.player = enter_params["player"]
        self.essence = enter_params["essence"]
        self.enemy = enter_params["enemy"]
        self.enemy_color = enter_params["enemy_color"]
        self.enemy_sprite = enter_params["enemy_sprite"]
        self.controller = enter_params["controller"]
        self.player_sprite = settings.TEXTURES[settings.PLAYER_SPRITE_FILE]

        self.selected: Optional[Tuple[int, int]] = None
        self.active = True
        self.turn_catalysis = False
        self.power_rects = []

    # -- Update / render -------------------------------------------------

    def render(self, surface: pygame.Surface) -> None:
        self.board.render(surface)

        if self.selected is not None:
            i, j = self.selected
            rect = pygame.Rect(
                self.board.x + j * settings.TILE_SIZE,
                self.board.y + i * settings.TILE_SIZE,
                settings.TILE_SIZE,
                settings.TILE_SIZE,
            )
            pygame.draw.rect(surface, (255, 255, 255), rect, width=3, border_radius=6)

        self._render_combat_zone(surface)
        self.power_rects = hud.draw_power_bar(surface, self.essence, self.controller.enemy_stunned)

    def _render_combat_zone(self, surface: pygame.Surface) -> None:
        player_portrait = pygame.Rect(16, 12, 64, 64)
        enemy_portrait = pygame.Rect(settings.VIRTUAL_WIDTH - 80, 12, 64, 64)
        hud.draw_portrait(
            surface, player_portrait, (70, 120, 200), self.player.name, self.player_sprite
        )
        hud.draw_portrait(
            surface, enemy_portrait, self.enemy_color, self.enemy.name, self.enemy_sprite
        )

        player_hp_rect = pygame.Rect(16, 92, 180, 16)
        enemy_hp_rect = pygame.Rect(settings.VIRTUAL_WIDTH - 196, 92, 180, 16)
        hud.draw_hp_bar(surface, player_hp_rect, "HP", self.player.hp, self.player.max_hp)
        hud.draw_hp_bar(surface, enemy_hp_rect, "HP", self.enemy.hp, self.enemy.max_hp)

        hud.draw_essence_row(surface, 16, 122, self.essence)

        turn_label = "Tu turno" if self.active else "..."
        render_text(
            surface,
            turn_label,
            settings.FONTS["small"],
            settings.VIRTUAL_WIDTH // 2,
            4,
            (235, 235, 240),
            center=True,
            shadowed=True,
        )

        hud.draw_log(surface, 16, 138, self.controller.log)

    # -- Input ------------------------------------------------------------

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if input_id == "click" and input_data.pressed:
            self._on_click(input_data.position)
        elif input_id == "power_fire" and input_data.pressed:
            self._try_power("fire")
        elif input_id == "power_shield" and input_data.pressed:
            self._try_power("shield")
        elif input_id == "power_stasis" and input_data.pressed:
            self._try_power("stasis")

    def _on_click(self, position: Tuple[int, int]) -> None:
        pos_x = position[0] * settings.VIRTUAL_WIDTH // settings.WINDOW_WIDTH
        pos_y = position[1] * settings.VIRTUAL_HEIGHT // settings.WINDOW_HEIGHT

        for power_id, rect in zip(POWERS.keys(), self.power_rects):
            if rect.collidepoint(pos_x, pos_y):
                self._try_power(power_id)
                return

        if not self.active or not settings.BOARD_ZONE.collidepoint(pos_x, pos_y):
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

    def _try_power(self, power_id: str) -> None:
        if not self.active or self.controller.game_over:
            return

        self.controller.activate_power(power_id)

        if self.controller.game_over:
            self._finish_combat()

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

            self.turn_catalysis = False
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
        kind_counts, catalysis, _cleared_count = self.board.resolve_runs(runs)

        if catalysis:
            self.turn_catalysis = True
            self.controller.log_message("Catalisis: linea despejada, turno extra")

        self.controller.apply_kind_effects(kind_counts)

        falling = self.board.get_falling_tiles()
        Timer.tween(0.25, falling, on_finish=self._after_fall)

    def _after_fall(self) -> None:
        if self.controller.game_over:
            self._finish_combat()
            return

        runs = self.board.find_matches()

        if runs:
            self._process_matches(runs)
        else:
            self._end_player_action()

    # -- Turn flow -------------------------------------------------------

    def _end_player_action(self) -> None:
        if self.turn_catalysis:
            self.active = True
        else:
            self._start_enemy_turn()

    def _start_enemy_turn(self) -> None:
        self.active = False
        Timer.after(settings.ENEMY_TURN_DELAY, self._do_enemy_turn)

    def _do_enemy_turn(self) -> None:
        self.controller.run_enemy_turn()

        if self.controller.game_over:
            self._finish_combat()
        else:
            self.active = True

    def _finish_combat(self) -> None:
        self.active = False

        if self.controller.victory and self.level < ENEMY_COUNT:
            # Beat this foe but the roster isn't exhausted yet: carry
            # the player's HP and essence into the next battle instead
            # of ending the run.
            Timer.after(
                0.6,
                lambda: self.state_machine.change(
                    "begin", level=self.level + 1, player=self.player, essence=self.essence
                ),
            )
            return

        victory = self.controller.victory
        level = self.level
        Timer.after(
            0.5, lambda: self.state_machine.change("game-over", victory=victory, level=level)
        )
