"""
This file contains the class TransmutacionArcana, the gale.game.Game
specialization that owns the top-level state machine (menu, match-3
play).
"""

import pygame

from gale.game import Game
from gale.input_handler import InputData
from gale.state import StateMachine

import settings
from src import states


class TransmutacionArcana(Game):
    def init(self) -> None:
        settings.play_background_music()

        self.state_machine = StateMachine(
            {
                "start": states.StartState,
                "play": states.PlayState,
            }
        )
        self.state_machine.change("start")

    def update(self, dt: float) -> None:
        self.state_machine.update(dt)

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(settings.BACKGROUND_COLOR)
        self.state_machine.render(surface)

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if input_id == "quit" and input_data.pressed:
            self.quit()
        else:
            self.state_machine.on_input(input_id, input_data)
