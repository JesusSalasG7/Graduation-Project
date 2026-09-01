"""
Entry point for Conway's Puzzle: a puzzle game built on Conway's Game
of Life (rule B3/S23), using the Gale engine on top of Pygame.
"""
import settings
from src.game import ConwayGame

if __name__ == "__main__":
    game = ConwayGame(
        settings.TITLE,
        settings.WINDOW_WIDTH,
        settings.WINDOW_HEIGHT,
        settings.VIRTUAL_WIDTH,
        settings.VIRTUAL_HEIGHT,
        settings.FPS,
    )
    game.exec()
