"""
Pure view: draws a Level's grid (walls, goal, obstacles) and a Player as
flat pygame rects. Knows nothing about input or movement rules -- see
src/entities/player.py and src/states/play_state.py for those.
"""
import pygame

import settings
from src.entities.player import Player
from src.world.level import Level


class GridRenderer:
    def render(self, surface: pygame.Surface, level: Level, player: Player) -> None:
        surface.fill(settings.BACKGROUND_COLOR)
        self._render_cells(surface, level)
        self._render_player(surface, player)

    def _render_cells(self, surface: pygame.Surface, level: Level) -> None:
        cell_size = settings.CELL_SIZE
        for row in range(level.rows):
            for col in range(level.columns):
                rect = pygame.Rect(col * cell_size, row * cell_size, cell_size, cell_size)
                if level.is_wall(row, col):
                    pygame.draw.rect(surface, settings.WALL_COLOR, rect)
                elif level.is_goal(row, col):
                    pygame.draw.rect(surface, settings.GOAL_COLOR, rect)
                elif level.is_obstacle(row, col):
                    pygame.draw.rect(surface, settings.OBSTACLE_COLOR, rect)

    def _render_player(self, surface: pygame.Surface, player: Player) -> None:
        cell_size = settings.CELL_SIZE
        # player.x/y are float cell coordinates, mid-slide included --
        # scaling them straight to pixels is what makes the slide read
        # as continuous motion instead of a cell-to-cell jump.
        rect = pygame.Rect(
            round(player.x * cell_size), round(player.y * cell_size), cell_size, cell_size
        )
        pygame.draw.rect(surface, settings.PLAYER_COLOR, rect)
