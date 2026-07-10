
import pygame

import settings


class Tile:
    """
    A single fragment of the puzzle picture used by PuzzleState.

    A Tile's `id` (and its `frame`, always equal to `id`) is fixed for its
    whole life: it identifies which piece of the source image the tile
    shows. Sorting the puzzle never changes `id` or `frame` — it only
    changes which board slot (i, j / x, y) the tile is placed in and how
    many times it has been rotated.

    `target_i`, `target_j` and `target_rotation` say where this specific
    fragment must end up (board slot + rotation) to reveal the hidden
    picture; that destination does not need to match the fragment's own
    origin slot (see SortingPuzzle.SOLUTION). The puzzle is solved when
    every tile reaches its own target (`is_correct_position`).
    """

    def __init__(
        self,
        x: int,
        y: int,
        frame: int,
        id: int,
        target_i: int,
        target_j: int,
        target_rotation: int = 0,
    ) -> None:
        self.x = x
        self.y = y
        self.i = self.y // settings.TILE_SIZE
        self.j = self.x // settings.TILE_SIZE
        self.frame = frame
        self.id = id
        self.target_i = target_i
        self.target_j = target_j
        self.target_rotation = target_rotation
        # Giros de 90° en sentido horario acumulados (0 a 3).
        self.rotation = 0

    @property
    def target_index(self) -> int:
        """Índice de tablero (fila*ancho + columna) de la casilla destino."""
        return self.target_i * settings.BOARD_WIDTH + self.target_j

    def is_correct_position(self) -> bool:
        """True si esta ficha está en su casilla y rotación de destino."""
        return (
            self.i == self.target_i
            and self.j == self.target_j
            and self.rotation == self.target_rotation
        )

    def get_rect(self) -> pygame.Rect:
        return pygame.Rect(
            self.x + settings.BOARD_OFFSET_X,
            self.y + settings.BOARD_OFFSET_Y,
            settings.TILE_SIZE,
            settings.TILE_SIZE,
        )

    def render(self, surface: pygame.Surface) -> None:
        image = settings.TEXTURES["Puzzle"].subsurface(settings.FRAMES["Puzzle"][self.frame])
        if self.rotation:
            image = pygame.transform.rotate(image, -90 * self.rotation)
        surface.blit(image, self.get_rect())
