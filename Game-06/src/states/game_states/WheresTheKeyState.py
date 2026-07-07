
import pygame

from gale.input_handler import InputData
from gale.state import BaseState
from gale.text import render_text

import settings
from src.states import game_states


class WheresTheKeyState(BaseState):
    """Interstitial screen that announces the boss-key puzzle minigame."""

    def enter(self, player) -> None:
        self.player = player

    def render(self, surface: pygame.Surface) -> None:
        surface.fill((51, 25, 102))

        render_text(
            surface,
            "¿DONDE ESTA LA LLAVE?",
            settings.FONTS["medium"],
            settings.VIRTUAL_WIDTH // 2,
            settings.VIRTUAL_HEIGHT // 2 - 20,
            (245, 191, 66),
            center=True,
            shadowed=True,
        )

        render_text(
            surface,
            "Resuelve el rompecabezas para encontrarla",
            settings.FONTS["small"],
            settings.VIRTUAL_WIDTH // 2,
            settings.VIRTUAL_HEIGHT // 2 + 10,
            (197, 195, 198),
            center=True,
            shadowed=True,
        )

        render_text(
            surface,
            "Presiona ENTER para comenzar",
            settings.FONTS["small"],
            settings.VIRTUAL_WIDTH // 2,
            settings.VIRTUAL_HEIGHT - 20,
            (197, 195, 198),
            center=True,
            shadowed=True,
        )

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if input_id == "enter" and input_data.pressed:
            self.state_machine.pop()
            self.state_machine.push(
                game_states.PuzzleState(self.state_machine), player=self.player
            )
