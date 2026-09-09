"""
Transmutacion Arcana

Entry point. ArcaneTransmutationGame takes every gale.game.Game argument
(title, window size, ...) straight from settings.py / gale.conf's
global settings, so there's no need to pass any of them here.
"""

from src.transmutacion_arcana import ArcaneTransmutationGame

if __name__ == "__main__":
    game = ArcaneTransmutationGame()
    game.exec()
