
import pygame

from gale.input_handler import InputData
from gale.state import BaseState
from gale.text import render_text

from src.states import game_states

import settings

class WinerLevelState(BaseState):
    def enter(self,level) -> None:
        self.level = level
        settings.SOUNDS["win_level"].play()

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if input_id == "enter" and input_data.pressed:
            settings.SOUNDS["win_level"].stop()
            self.state_machine.pop()
            self.state_machine.push(game_states.PlayState(self.state_machine), level=self.level)

    def render(self, surface: pygame.Surface) -> None:

        if self.level == 1:
            surface.fill((100, 100, 100))
        else:
            surface.fill((51, 25, 102))  

        render_text(
            surface,
            "Winner",
            settings.FONTS["medium"],
            settings.VIRTUAL_WIDTH // 2,
            20,
            (255, 255, 255),
            center=True,
            shadowed=True,
        )

        surface.blit(
            settings.TEXTURES["dead"],
            (settings.VIRTUAL_WIDTH // 2 - 16 , settings.VIRTUAL_HEIGHT // 2),
            settings.FRAMES["dead"][0],
        )

        render_text(
            surface,
            "Press Enter to next level",
            settings.FONTS["small"],
            settings.VIRTUAL_WIDTH // 2,
            settings.VIRTUAL_HEIGHT - 20,
            (255, 255, 255),
            center=True,
            shadowed=True,
        )
