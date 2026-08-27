"""
The only state this prototype needs: builds a fresh procedurally
generated Level on enter (and again on "regenerate"), each frame feeds
player input against it -- including reacting to the goal and to
obstacle hazards via Player.update's on_enter_cell hook -- and delegates
grid/entity drawing to GridRenderer, adding only the small HUD overlay on
top.
"""
from typing import Any, Dict, Tuple

import pygame

from gale.input_handler import InputData
from gale.state import BaseState

import settings
from src.entities.player import DOWN, LEFT, RIGHT, UP, Player
from src.rendering.grid_renderer import GridRenderer
from src.world.level import generate_playable_level

_DIRECTIONS = {
    "move_up": UP,
    "move_down": DOWN,
    "move_left": LEFT,
    "move_right": RIGHT,
}


class PlayState(BaseState):
    def enter(self, *args: Tuple[Any], **kwargs: Dict[str, Any]) -> None:
        self.renderer = GridRenderer()
        self._new_level()

    def _new_level(self) -> None:
        self.level = generate_playable_level(
            settings.GRID_COLUMNS,
            settings.GRID_ROWS,
            settings.CA_WALL_PROBABILITY,
            settings.CA_ITERATIONS,
            settings.CA_BIRTH_LIMIT,
            settings.CA_SURVIVE_MIN,
            settings.CA_SURVIVE_MAX,
            settings.CA_MIN_OPEN_CELLS,
            settings.CA_MIN_GOAL_DISTANCE,
            settings.OBSTACLE_DENSITY,
            settings.OBSTACLE_SAFE_RADIUS,
            settings.CA_MAX_GENERATION_ATTEMPTS,
        )
        self.player = Player(
            self.level.spawn_col, self.level.spawn_row, settings.PLAYER_SPEED_CELLS_PER_SECOND
        )
        self._attempts = 0
        self._won = False

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if not input_data.pressed:
            return

        if input_id == "regenerate":
            self._new_level()
        elif not self._won and input_id in _DIRECTIONS:
            self.player.try_move(_DIRECTIONS[input_id])

    def _on_enter_cell(self, row: int, col: int) -> bool:
        if self.level.is_goal(row, col):
            self._won = True
            return True

        if self.level.is_obstacle(row, col):
            self._attempts += 1
            self.player.warp_to(self.level.spawn_col, self.level.spawn_row)
            return True

        return False

    def update(self, dt: float) -> None:
        if self._won:
            return
        self.player.update(dt, self.level.is_wall, self._on_enter_cell)

    def render(self, surface: pygame.Surface) -> None:
        self.renderer.render(surface, self.level, self.player)
        self._render_hud(surface)

    def _render_hud(self, surface: pygame.Surface) -> None:
        hud_text = settings.FONTS["hud"].render(
            f"Intentos: {self._attempts}    R: nuevo laberinto", True, settings.HUD_TEXT_COLOR
        )
        surface.blit(hud_text, (4, 4))

        if self._won:
            banner = settings.FONTS["banner"].render(
                "META ALCANZADA -- presiona R", True, settings.WIN_BANNER_COLOR
            )
            rect = banner.get_rect(center=(settings.VIRTUAL_WIDTH // 2, settings.VIRTUAL_HEIGHT // 2))
            surface.blit(banner, rect)
