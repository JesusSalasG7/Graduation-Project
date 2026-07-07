
import pygame

from gale.input_handler import InputData
from gale.state import BaseState
from gale.text import render_text

from gale.animation import Animation
from src.states import game_states


import settings

class FinalState(BaseState):
    def enter(self,level) -> None:
        self.level = level

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if input_id == "enter" and input_data.pressed:
            self.state_machine.pop()
            self.state_machine.push(game_states.PlayState(self.state_machine), level=2)

    def render(self, surface: pygame.Surface) -> None:

        surface.fill((51, 25, 102))

        render_text(
            surface,
            "FIN",
            settings.FONTS["medium"],
            settings.VIRTUAL_WIDTH // 2,
            settings.VIRTUAL_HEIGHT // 2 - 20,
            (255, 255, 255),
            center=True,
            shadowed=True,
        )

        render_text(
            surface,
            "Gracias por jugar",
            settings.FONTS["small"],
            settings.VIRTUAL_WIDTH // 2,
            settings.VIRTUAL_HEIGHT // 2 + 10,
            (197, 195, 198),
            center=True,
            shadowed=True,
        )

        render_text(
            surface,
            "Presiona ENTER para jugar de nuevo",
            settings.FONTS["small"],
            settings.VIRTUAL_WIDTH // 2,
            settings.VIRTUAL_HEIGHT - 20,
            (197, 195, 198),
            center=True,
            shadowed=True,
        )

