"""
Entry point for the Snake game.
"""
import settings
from src.snake_game import SnakeGame

if __name__ == "__main__":
    game = SnakeGame(
        "Snake",
        settings.WINDOW_WIDTH,
        settings.WINDOW_HEIGHT,
        settings.VIRTUAL_WIDTH,
        settings.VIRTUAL_HEIGHT,
    )
    game.exec()
