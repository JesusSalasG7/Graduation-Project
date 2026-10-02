"""
Main game class: creates the StateMachine, enters the 'menu' state
(the title screen), and forwards input to whichever state is
currently active.
"""
import pygame

from gale.game import Game
from gale.input_handler import InputData, InputListener
from gale.state import StateMachine

from src import text
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

    def _Game__render(self) -> None:
        # Overrides gale's private Game.__render (the loop calls it as
        # self.__render(), i.e. self._Game__render()): same steps, plus
        # drawing the text queued by src.text.render_text straight onto
        # the window AFTER the virtual canvas is upscaled, so it stays
        # sharp instead of being scaled up ~3-4x with everything else.
        text.begin_frame()
        self.render_surface.fill((0, 0, 0))
        self.render(self.render_surface)
        self.screen.blit(pygame.transform.scale(self.render_surface, self.screen.get_size()), (0, 0))
        text.flush(
            self.screen,
            self.screen.get_width() / self.virtual_width,
            self.screen.get_height() / self.virtual_height,
        )
        pygame.display.update()

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if input_id == 'quit' and input_data.pressed:
            self.quit()
            return

        self.state_machine.on_input(input_id, input_data)
