"""
PlayState: the main puzzle screen. The player spends a cell budget
placing live cells on the grid, then runs Conway's Game of Life
(B3/S23) hoping the resulting pattern satisfies the level's victory
condition (reach the target zone, or wipe out an enemy pattern).

Controls:
    Mouse click  -- place/remove a cell (only before the simulation
                    has taken its first step).
    SPACE        -- toggle pause/play of the automatic simulation.
    S            -- advance exactly one generation.
    R            -- clear every player-placed cell (pre-simulation only).
    ENTER        -- restart the level from scratch.
    ESC          -- back to the level menu.
"""
from typing import Any, Dict, Tuple

import pygame

from gale.input_handler import InputData
from gale.state import BaseState

import settings
from src.board import Board
from src.levels import LEVELS
from src.rendering.board_renderer import BoardRenderer
from src.rendering.hud_renderer import render_hud


class PlayState(BaseState):
    def __init__(self, state_machine, game) -> None:
        super().__init__(state_machine)
        self.game = game
        self.renderer = BoardRenderer()

    def enter(self, *args: Tuple[Any], level_index: int = 0, **kwargs: Dict[str, Any]) -> None:
        self.level_index = level_index
        self._load_level()

    def _load_level(self) -> None:
        level = LEVELS[self.level_index]
        self.level = level
        self.board = Board(
            settings.GRID_COLUMNS,
            settings.GRID_ROWS,
            level.walls,
            level.target_zone,
            level.enemy_cells,
            level.budget,
        )
        self._set_running(False)
        self.time_since_step = 0.0
        self.hover_cell = None

    def _set_running(self, running: bool) -> None:
        """
        Flip the simulation on/off and keep the background music in sync
        with it: playing (looped) exactly while the simulation runs,
        stopped the instant it doesn't -- whether that's the player
        pausing it, stepping once, or a level's win condition ending it.
        """
        self.running_sim = running
        if running:
            if not pygame.mixer.music.get_busy():
                pygame.mixer.music.load(settings.BACKGROUND_MUSIC_PATH)
                pygame.mixer.music.play(loops=-1)
        else:
            pygame.mixer.music.stop()

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if input_id == "back":
            if input_data.pressed:
                self.state_machine.change("start")
            return

        if input_id == "confirm":
            if input_data.pressed:
                self._load_level()
            return

        if input_id == "toggle_pause":
            if input_data.pressed:
                self._set_running(not self.running_sim)
            return

        if input_id == "step_once":
            if input_data.pressed:
                self._set_running(False)
                self._step()
            return

        if input_id == "clear_cells":
            if input_data.pressed and self.board.generation == 0:
                self.board.clear_player_cells()
            return

        if input_id == "mouse_move":
            self.hover_cell = self.renderer.cell_at_pixel(*input_data.position)
            return

        if input_id == "place_cell":
            if input_data.pressed and self.board.generation == 0:
                col, row = self.renderer.cell_at_pixel(*input_data.position)
                if self.board.toggle_cell(col, row):
                    self.game.achievements.on_cell_placed(len(self.board.player_cells))
            return

    def update(self, dt: float) -> None:
        if self.running_sim:
            self.time_since_step += dt
            while self.time_since_step >= settings.GENERATION_INTERVAL:
                self.time_since_step -= settings.GENERATION_INTERVAL
                self._step()
                if not self.running_sim:
                    break

        self.game.achievements.update(dt)

    def _step(self) -> None:
        births = self.board.step()
        self.game.achievements.on_generation(births)

        if self._victory_reached():
            self._set_running(False)
            self.game.achievements.on_victory(
                self.board.budget_total, self.board.budget_remaining
            )
            self.game.show_victory(
                self.level_index,
                generation=self.board.generation,
                budget_used=self.board.budget_total - self.board.budget_remaining,
                budget_total=self.board.budget_total,
            )

    def _victory_reached(self) -> bool:
        if self.level.win_type == "target":
            return self.board.reached_target()
        return self.board.enemies_eliminated()

    def render(self, surface: pygame.Surface) -> None:
        hover = self.hover_cell if self.board.generation == 0 else None
        self.renderer.render(surface, self.board, hover_cell=hover)
        render_hud(
            surface,
            self.level_index,
            len(LEVELS),
            self.level.name,
            self.board.generation,
            self.board.budget_remaining,
            self.board.budget_total,
            self.running_sim,
        )
        self.game.achievements.render(surface)
