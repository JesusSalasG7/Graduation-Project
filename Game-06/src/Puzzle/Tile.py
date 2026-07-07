
import pygame

import settings


class Tile:
    """A single 2x2 fragment used by the "Where's the Key" puzzle (PuzzleState)."""

    def __init__(self, x: int, y: int, frame: int, id: int) -> None:
        self.x = x
        self.y = y
        self.i = self.y // settings.TILE_SIZE
        self.j = self.x // settings.TILE_SIZE
        self.frame = frame
        # Fixed creation-order index (0..3); identifies which fragment this
        # is regardless of where it currently sits on the board.
        self.id = id
        self.rotation = 0

    def get_rect(self) -> pygame.Rect:
        return pygame.Rect(
            self.x + settings.BOARD_OFFSET_X,
            self.y + settings.BOARD_OFFSET_Y,
            settings.TILE_SIZE,
            settings.TILE_SIZE,
        )

    def rotate(self) -> None:
        self.rotation = (self.rotation + 90) % 360

    def render(self, surface: pygame.Surface) -> None:
        rotated_image = pygame.transform.rotate(
            settings.TEXTURES["Puzzle"].subsurface(settings.FRAMES["Puzzle"][self.frame]),
            self.rotation,
        )
        surface.blit(rotated_image, self.get_rect())
