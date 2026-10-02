"""
This file contains the class ArcaneTransmutationGame, the gale.game.Game
specialization that owns the top-level state machine (menu, how-to-play
guide, match-3 play).
"""

import pygame

from gale.game import Game
from gale.input_handler import InputData
from gale.state import StateMachine

import settings
from src import states, text


class ArcaneTransmutationGame(Game):
    def init(self) -> None:
        settings.play_background_music()

        self.state_machine = StateMachine(
            {
                "start": states.StartState,
                "play": states.PlayState,
                "guide": states.GuideState,
            }
        )
        self.state_machine.change("start")

    def update(self, dt: float) -> None:
        self.state_machine.update(dt)

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(settings.BACKGROUND_COLOR)
        self.state_machine.render(surface)

    def _Game__render(self) -> None:
        # Overrides gale's private Game.__render (the loop calls it as
        # self.__render(), i.e. self._Game__render()): same steps, plus
        # drawing the text queued by src.text.render_text straight onto
        # the window AFTER the virtual canvas is upscaled, so it stays
        # sharp instead of being scaled up with everything else.
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
        if input_id == "quit" and input_data.pressed:
            self.quit()
        else:
            self.state_machine.on_input(input_id, input_data)
