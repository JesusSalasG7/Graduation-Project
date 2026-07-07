
import settings
from src.Board import Board

if __name__ == "__main__":
    board = Board(
        "Puzzle",
        settings.WINDOW_WIDTH,
        settings.WINDOW_HEIGHT,
        settings.VIRTUAL_WIDTH,
        settings.VIRTUAL_HEIGHT,
    )
    board.exec()
