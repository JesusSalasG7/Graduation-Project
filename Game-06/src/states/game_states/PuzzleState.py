
import math

import pygame

from gale.input_handler import InputData
from gale.state import BaseState
from gale.text import render_text

import settings
from src.Puzzle.SortingPuzzle import SortingPuzzle

UNSOLVED_COLOR = (231, 76, 60)  # rojo
SOLVED_COLOR = (46, 204, 113)  # verde
KEY_DELAY_SECONDS = 5


class PuzzleState(BaseState):
    """
    "Where's the Key" minigame: a picture is cut into
    settings.BOARD_WIDTH x settings.BOARD_HEIGHT fragments, shown intact
    (matching the source image) at the start; the player must rearrange
    the fragments (position + rotation) into the hidden solution to
    reveal the key and face the boss.

    Game-lifecycle wiring:
        PlayState (el jugador toca el ítem llave)
            -> WheresTheKeyState ("Presiona ENTER para comenzar")
            -> PuzzleState.enter()   <- estás aquí

    Dónde vive el ordenamiento:
        El algoritmo de ordenamiento NO está en este archivo. Vive en
        SortingPuzzle.sort() (src/Puzzle/SortingPuzzle.py), que reordena
        una lista de fragmentos Tile (src/Puzzle/Tile.py) según la
        casilla de destino de cada uno. PuzzleState solo se encarga del
        lado pygame: le pide a SortingPuzzle los Tile ya armados
        (SortingPuzzle.new_tiles()), le pide que los ordene, traduce el
        orden resultante en posiciones de tablero (__place_tiles) y lo
        dibuja. Nada de esto necesita cambiar para la tarea del estudiante.
    """

    def enter(self, player) -> None:
        self.player = player
        self.solved = False
        # Segundos restantes antes de entregar la llave una vez resuelto;
        # None mientras el puzzle no está resuelto (ver __solve/update).
        self.key_countdown = None

        # SortingPuzzle.new_tiles() crea cada Tile en su casilla de
        # origen (imagen intacta, tal cual el asset) junto con la
        # casilla+rotación de destino que no necesariamente coincide con
        # ese origen (ver SortingPuzzle.SOLUTION). sort() es quien debe
        # llevar cada ficha de su origen a su destino.
        tiles = SortingPuzzle.new_tiles()
        self.puzzle = SortingPuzzle(tiles)
        self.__place_tiles()

        self.screen_alpha_surface = pygame.Surface(
            (settings.VIRTUAL_WIDTH, settings.VIRTUAL_HEIGHT), pygame.SRCALPHA
        )

        # --------------------------------------------------------------
        # Llamada de validación del desarrollador.
        #
        # Se invoca el algoritmo apenas se entra a este estado para
        # comprobar, de forma visual e inmediata, que el tablero, el
        # render y el flujo de victoria (entrega de la llave) funcionan
        # de punta a punta ANTES de dejar SortingPuzzle.sort() vacío para
        # que el estudiante lo programe.
        #
        # Cuando sort() se vacíe, self.puzzle.tiles seguirá desordenado
        # y la imagen se mostrará incompleta/desordenada hasta que el
        # estudiante complete el algoritmo correctamente y vuelva a
        # ejecutar el juego.
        # --------------------------------------------------------------
        self.puzzle.sort()
        self.__place_tiles()

        if self.puzzle.is_sorted():
            self.__solve()

    def __place_tiles(self) -> None:
        """
        Traduce el orden actual de self.puzzle.tiles en posiciones de
        tablero: el tile en el índice `k` de la lista pasa a ocupar la
        casilla `k` del tablero (fila por fila). Esto es lo único que
        conecta "el arreglo está ordenado" con "la imagen se ve armada".
        """
        for index, tile in enumerate(self.puzzle.tiles):
            row, col = divmod(index, settings.BOARD_WIDTH)
            tile.i, tile.j = row, col
            tile.x = col * settings.TILE_SIZE
            tile.y = row * settings.TILE_SIZE

    def __solve(self) -> None:
        self.solved = True
        self.key_countdown = KEY_DELAY_SECONDS

    def __grant_key(self) -> None:
        self.player.pickup_key = True
        settings.SOUNDS["pickup_coin"].stop()
        settings.SOUNDS["pickup_coin"].play()
        self.state_machine.pop()

    def update(self, dt: float) -> None:
        if self.key_countdown is None:
            return

        self.key_countdown -= dt
        if self.key_countdown <= 0:
            self.key_countdown = None
            self.__grant_key()

    def render(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(
            self.screen_alpha_surface,
            (128, 128, 128, 180),
            pygame.Rect(0, 0, settings.VIRTUAL_WIDTH, settings.VIRTUAL_HEIGHT),
        )
        surface.blit(self.screen_alpha_surface, (0, 0))

        for tile in self.puzzle.tiles:
            tile.render(surface)

        render_text(
            surface,
            "RESUELTO" if self.solved else "NO RESUELTO",
            settings.FONTS["small"],
            settings.VIRTUAL_WIDTH // 2,
            10,
            SOLVED_COLOR if self.solved else UNSOLVED_COLOR,
            center=True,
            shadowed=True,
        )

        if self.key_countdown is not None:
            render_text(
                surface,
                f"Llave en {math.ceil(self.key_countdown)}...",
                settings.FONTS["small"],
                settings.VIRTUAL_WIDTH // 2,
                20,
                (245, 191, 66),
                center=True,
                shadowed=True,
            )

    def on_input(self, input_id: str, input_data: InputData) -> None:
        # Este puzzle se resuelve por completo mediante código
        # (SortingPuzzle.sort()); no hay nada que el jugador deba
        # clickear, arrastrar o rotar.
        pass
