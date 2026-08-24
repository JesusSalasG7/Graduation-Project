"""
This file contains the class StartState: the title screen. It shows
the cover art (assets/graphics/ui/cover.jpg, settings.COVER_IMAGE_PATH)
full-screen; pressing Enter fades out into the match-3 board
(PlayState). Esc still quits from here -- that's handled unconditionally
at the Game level (see src/transmutacion_arcana.py), not by this state.
"""

import pygame

from gale.input_handler import InputData
from gale.state import BaseState, StateMachine
from gale.timer import Timer

import settings


class StartState(BaseState):
    def __init__(self, state_machine: StateMachine) -> None:
        super().__init__(state_machine)

    def enter(self) -> None:
        self.active = True
        self.alpha_transition = 0

        cover = pygame.image.load(settings.COVER_IMAGE_PATH).convert()
        self.cover = pygame.transform.smoothscale(
            cover, (settings.VIRTUAL_WIDTH, settings.VIRTUAL_HEIGHT)
        )
        self.screen_alpha_surface = pygame.Surface(
            (settings.VIRTUAL_WIDTH, settings.VIRTUAL_HEIGHT), pygame.SRCALPHA
        )

    def render(self, surface: pygame.Surface) -> None:
        surface.blit(self.cover, (0, 0))

        pygame.draw.rect(
            self.screen_alpha_surface,
            (255, 255, 255, self.alpha_transition),
            pygame.Rect(0, 0, settings.VIRTUAL_WIDTH, settings.VIRTUAL_HEIGHT),
        )
        surface.blit(self.screen_alpha_surface, (0, 0))

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if not self.active:
            return

        if input_id == "enter" and input_data.pressed:
            self.active = False
            Timer.tween(
                0.5,
                [(self, {"alpha_transition": 255})],
                on_finish=lambda: self.state_machine.change("play"),
            )
