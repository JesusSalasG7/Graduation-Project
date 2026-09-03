"""
BoardRenderer: draws a Board's logic grid to pixels. This is the only
place in the codebase that converts (col, row) into screen coordinates
-- Board itself never touches pygame.Rect or a pixel value.
"""
from typing import Optional, Tuple

import pygame

import settings
from src.board import Board

Coord = Tuple[int, int]


class BoardRenderer:
    def __init__(self, origin_y: int = settings.HUD_HEIGHT) -> None:
        self.origin_y = origin_y
        self.cell_size = settings.CELL_SIZE

    def cell_at_pixel(self, window_x: int, window_y: int) -> Coord:
        """
        Convert a raw pygame mouse position (in real window pixels) into
        a (col, row) on the logic grid, undoing the window/virtual-
        surface scale Game.exec applies when blitting render_surface.
        """
        x = window_x / settings.WINDOW_SCALE
        y = window_y / settings.WINDOW_SCALE
        return (int(x) // self.cell_size, int(y - self.origin_y) // self.cell_size)

    def _cell_rect(self, col: int, row: int) -> pygame.Rect:
        return pygame.Rect(
            col * self.cell_size,
            self.origin_y + row * self.cell_size,
            self.cell_size,
            self.cell_size,
        )

    def render(
        self, surface: pygame.Surface, board: Board, hover_cell: Optional[Coord] = None
    ) -> None:
        area = pygame.Rect(
            0, self.origin_y, board.columns * self.cell_size, board.rows * self.cell_size
        )
        surface.fill(settings.BACKGROUND_COLOR, area)

        for col, row in board.target_zone:
            color = (
                settings.TARGET_ZONE_ALIVE_COLOR
                if board.is_alive(col, row)
                else settings.TARGET_ZONE_COLOR
            )
            surface.fill(color, self._cell_rect(col, row))

        for col, row in board.walls:
            surface.fill(settings.WALL_COLOR, self._cell_rect(col, row))

        for col, row in board.alive_cells():
            color = (
                settings.ENEMY_CELL_COLOR
                if (col, row) in board.enemy_cells
                else settings.PLAYER_CELL_COLOR
            )
            surface.fill(color, self._cell_rect(col, row))

        for col in range(board.columns + 1):
            x = col * self.cell_size
            pygame.draw.line(
                surface,
                settings.GRID_LINE_COLOR,
                (x, self.origin_y),
                (x, self.origin_y + board.rows * self.cell_size),
            )
        for row in range(board.rows + 1):
            y = self.origin_y + row * self.cell_size
            pygame.draw.line(
                surface, settings.GRID_LINE_COLOR, (0, y), (board.columns * self.cell_size, y)
            )

        if hover_cell is not None:
            col, row = hover_cell
            if board.in_bounds(col, row) and not board.is_wall(col, row):
                pygame.draw.rect(
                    surface, settings.CURSOR_COLOR, self._cell_rect(col, row), width=2
                )
