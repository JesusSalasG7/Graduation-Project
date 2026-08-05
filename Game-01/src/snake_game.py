"""
The Game entry point wiring input handling to a StateMachine, following
gale's standard game/state architecture.
"""
import pygame

from gale.game import Game
from gale.input_handler import InputData, InputListener
from gale.state import StateMachine

from src.states.cover_state import CoverState
from src.states.menu_state import MenuState
from src.states.play_state import PlayState


class SnakeGame(Game, InputListener):
    def init(self) -> None:
        # Game.__init__ already registered `self` as a listener before
        # calling init() -- registering again here would make on_input
        # fire twice per event (e.g. a menu toggle that immediately
        # cancels itself out).
        self.state_machine = StateMachine(
            {"cover": CoverState, "menu": MenuState, "play": PlayState}
        )
        self.state_machine.change("cover")

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if input_id == "quit" and input_data.pressed:
            self.quit()
        else:
            self.state_machine.on_input(input_id, input_data)

    def update(self, dt: float) -> None:
        self.state_machine.update(dt)

    def render(self, surface: pygame.Surface) -> None:
        self.state_machine.render(surface)
