"""
Entry point for the procedural-maze slider prototype.
"""
import settings
from src.maze_slider_game import MazeSliderGame

if __name__ == "__main__":
    game = MazeSliderGame(
        settings.TITLE,
        settings.WINDOW_WIDTH,
        settings.WINDOW_HEIGHT,
        settings.VIRTUAL_WIDTH,
        settings.VIRTUAL_HEIGHT,
        settings.FPS,
    )
    game.exec()
