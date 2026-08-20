"""
Entry point for TypeBeat.
"""
import settings
from src.typing_beat_game import TypeBeatGame

if __name__ == "__main__":
    game = TypeBeatGame(
        "TypeBeat",
        settings.WINDOW_WIDTH,
        settings.WINDOW_HEIGHT,
        settings.VIRTUAL_WIDTH,
        settings.VIRTUAL_HEIGHT,
    )
    game.exec()
