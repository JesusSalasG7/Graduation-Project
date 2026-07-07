
from typing import Dict, Any

import pygame

from gale.input_handler import InputData
from gale.state import BaseState
from gale.text import render_text
from gale.timer import Timer

import settings


class PauseState(BaseState):
    def enter(self) -> None:
        pygame.mixer.music.pause()

    def exit(self) -> None:
        pygame.mixer.music.unpause()

    def render(self, surface: pygame.Surface) -> None:
        render_text(
            surface,
            "PAUSE",
            settings.FONTS["medium"],
            settings.VIRTUAL_WIDTH // 2,
            settings.VIRTUAL_HEIGHT // 2,
            (255, 255, 255),
            center=True,
            shadowed=True,
        )


    def on_input(self, input_id: str, input_data: InputData) -> None:
        if input_id == "pause" and input_data.pressed:
            Timer.resume()
            self.state_machine.pop()
