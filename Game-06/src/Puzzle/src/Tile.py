
import pygame

import settings


class Tile:
    id_counter = 0

    def __init__(self, x: int, y: int, frame: int) -> None:
        self.x = x
        self.y = y
        self.i = self.y // settings.TILE_SIZE
        self.j = self.x // settings.TILE_SIZE
        self.frame = frame
        self.rotation = 0
        self.id = Tile.id_counter 
        Tile.id_counter += 1 
    
    def rotate(self) -> None:
        self.rotation = (self.rotation + 90) % 360

    def render(self, surface: pygame.Surface, rotate: bool) -> None:
        rotated_image = pygame.transform.rotate(
            settings.TEXTURES["Puzzle"].subsurface(settings.FRAMES["Puzzle"][self.frame]),
            self.rotation
        )
        surface.blit(
            rotated_image,
            (self.x + settings.BOARD_OFFSET_X, self.y + settings.BOARD_OFFSET_Y)
        )