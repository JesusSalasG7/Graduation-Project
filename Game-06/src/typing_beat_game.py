"""
The Game entry point wiring input handling to a StateMachine, following
gale's standard game/state architecture -- identical shape to Game-01's
src/snake_game.py, just with TypeBeat's own two states. There is no
menu/difficulty-select state: CoverState's ENTER drops straight into
PlayState (see src/states/cover_state.py).
"""
import pygame

from gale.game import Game
from gale.input_handler import InputData, InputListener
from gale.state import StateMachine

from src.rendering import pixel_text
from src.states.cover_state import CoverState
from src.states.play_state import PlayState


class TypeBeatGame(Game, InputListener):
    def init(self) -> None:
        # Game.__init__ already registered `self` as a listener before
        # calling init() -- registering again here would make on_input
        # fire twice per event.
        self.state_machine = StateMachine({"cover": CoverState, "play": PlayState})
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

    def _Game__render(self) -> None:
        # Overrides gale's private Game.__render (the loop calls it as
        # self.__render(), i.e. self._Game__render()): same steps, plus
        # drawing the text queued by pixel_text.render_text straight onto
        # the window AFTER the virtual canvas is upscaled, so it stays
        # sharp instead of being scaled up with everything else.
        pixel_text.begin_frame()
        self.render_surface.fill((0, 0, 0))
        self.render(self.render_surface)
        self.screen.blit(pygame.transform.scale(self.render_surface, self.screen.get_size()), (0, 0))
        pixel_text.flush(
            self.screen,
            self.screen.get_width() / self.virtual_width,
            self.screen.get_height() / self.virtual_height,
        )
        pygame.display.update()
