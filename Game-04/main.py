"""
Entry point for Mirror Code (Espejo de Códigos).
"""
import settings
from src.mirror_code_game import MirrorCodeGame

if __name__ == "__main__":
    game = MirrorCodeGame(
        settings.TITLE,
        settings.WINDOW_WIDTH,
        settings.WINDOW_HEIGHT,
        settings.VIRTUAL_WIDTH,
        settings.VIRTUAL_HEIGHT,
    )
    game.exec()
