"""
Main game class: creates the StateMachine, enters the 'menu' state
(the title screen), and forwards input to whichever state is
currently active.
"""
import pygame

from gale.game import Game
from gale.input_handler import InputData, InputListener
from gale.state import StateMachine

from src.states.instructions_state import InstructionsState
from src.states.menu_state import MenuState
from src.states.play_state import PlayState


class CubeGame(Game, InputListener):
    def init(self) -> None:
        self.state_machine = StateMachine({
            'menu': MenuState,
            'play': PlayState,
            'instructions': InstructionsState,
        })
        self.state_machine.change('menu')

    def update(self, dt: float) -> None:
        self.state_machine.update(dt)

    def render(self, surface: pygame.Surface) -> None:
        self.state_machine.render(surface)

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if input_id == 'quit' and input_data.pressed:
            self.quit()
            return

        self.state_machine.on_input(input_id, input_data)
