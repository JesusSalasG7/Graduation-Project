
import pygame

from gale.input_handler import InputData
from gale.state import BaseState
from gale.text import render_text
from gale.timer import Timer

import settings
from src.Puzzle.Tile import Tile


class PuzzleState(BaseState):
    """
    "Where's the Key" minigame: a 2x2 swap-and-rotate picture puzzle.
    Repositioning and rotating the four fragments reveals a hidden picture;
    solving it grants the player the key needed to face the boss.
    """

    SELECTED_BORDER_COLOR = (255, 215, 0)
    BORDER_WIDTH = 3

    # Tile.id (fixed creation order, row-major) -> the (row, col, rotation)
    # it must reach to reveal the hidden picture. Discovered by trial with
    # the reference implementation this puzzle was ported from.
    SOLUTION = {
        0: (0, 1, 0),
        1: (1, 0, 0),
        2: (0, 0, 180),
        3: (1, 1, 180),
    }

    def enter(self, player) -> None:
        self.player = player
        self.board = [
            [None for _ in range(settings.BOARD_WIDTH)]
            for _ in range(settings.BOARD_HEIGHT)
        ]
        self.__generate_board()

        self.screen_alpha_surface = pygame.Surface(
            (settings.VIRTUAL_WIDTH, settings.VIRTUAL_HEIGHT), pygame.SRCALPHA
        )

        # Currently selected tile (first click); swapped with the next tile
        # clicked, or rotated in place if clicked again.
        self.highlighted_tile = False
        self.highlighted_i1 = None
        self.highlighted_j1 = None

        self.active = True
        self.solved = False

    def __generate_board(self) -> None:
        value = 0
        for i in range(settings.BOARD_HEIGHT):
            for j in range(settings.BOARD_WIDTH):
                self.board[i][j] = Tile(
                    x=j * settings.TILE_SIZE,
                    y=i * settings.TILE_SIZE,
                    frame=value,
                    id=value,
                )
                value += 1

    def __check_to_win(self) -> bool:
        for row in self.board:
            for tile in row:
                target_row, target_col, target_rotation = self.SOLUTION[tile.id]
                if (
                    tile.i != target_row
                    or tile.j != target_col
                    or tile.rotation != target_rotation
                ):
                    return False
        return True

    def __solve(self) -> None:
        self.solved = True
        self.active = False
        Timer.after(2, self.__grant_key)

    def __grant_key(self) -> None:
        self.player.pickup_key = True
        settings.SOUNDS["pickup_coin"].stop()
        settings.SOUNDS["pickup_coin"].play()
        self.state_machine.pop()

    def render(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(
            self.screen_alpha_surface,
            (128, 128, 128, 180),
            pygame.Rect(0, 0, settings.VIRTUAL_WIDTH, settings.VIRTUAL_HEIGHT),
        )
        surface.blit(self.screen_alpha_surface, (0, 0))

        for row in self.board:
            for tile in row:
                tile.render(surface)

        if self.highlighted_tile:
            selected = self.board[self.highlighted_i1][self.highlighted_j1]
            pygame.draw.rect(
                surface,
                self.SELECTED_BORDER_COLOR,
                selected.get_rect(),
                self.BORDER_WIDTH,
            )

        if self.solved:
            render_text(
                surface,
                "¡Llave conseguida!",
                settings.FONTS["small"],
                settings.VIRTUAL_WIDTH // 2,
                10,
                (245, 191, 66),
                center=True,
                shadowed=True,
            )

    def on_input(self, input_id: str, input_data: InputData) -> None:
        # Left click is bound to the "attack" action; here it means "select
        # or swap a tile" instead, since this state owns all input while active.
        if not self.active or input_id != "attack" or not input_data.pressed:
            return

        pos_x, pos_y = input_data.position
        pos_x = pos_x * settings.VIRTUAL_WIDTH // settings.WINDOW_WIDTH
        pos_y = pos_y * settings.VIRTUAL_HEIGHT // settings.WINDOW_HEIGHT
        i = (pos_y - settings.BOARD_OFFSET_Y) // settings.TILE_SIZE
        j = (pos_x - settings.BOARD_OFFSET_X) // settings.TILE_SIZE

        if not (0 <= i < settings.BOARD_HEIGHT and 0 <= j < settings.BOARD_WIDTH):
            return

        i, j = int(i), int(j)

        if not self.highlighted_tile:
            self.highlighted_tile = True
            self.highlighted_i1 = i
            self.highlighted_j1 = j
            return

        if self.highlighted_i1 == i and self.highlighted_j1 == j:
            # Second click on the SAME tile: rotate it in place.
            self.board[i][j].rotate()
            self.highlighted_tile = False
            if self.__check_to_win():
                self.__solve()
            return

        di = abs(i - self.highlighted_i1)
        dj = abs(j - self.highlighted_j1)
        i1, j1 = self.highlighted_i1, self.highlighted_j1
        self.highlighted_tile = False

        if di <= 1 and dj <= 1 and di != dj:
            self.__swap(i1, j1, i, j)

    def __swap(self, i1: int, j1: int, i2: int, j2: int) -> None:
        self.active = False
        tile1 = self.board[i1][j1]
        tile2 = self.board[i2][j2]

        def arrive():
            self.board[i1][j1], self.board[i2][j2] = tile2, tile1
            tile1.i, tile1.j, tile2.i, tile2.j = i2, j2, i1, j1
            self.active = True
            if self.__check_to_win():
                self.__solve()

        Timer.tween(
            0.2,
            [
                (tile1, {"x": tile2.x, "y": tile2.y}),
                (tile2, {"x": tile1.x, "y": tile1.y}),
            ],
            on_finish=arrive,
        )
