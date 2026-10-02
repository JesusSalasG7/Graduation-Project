"""
This file contains the class StartState: the title screen. It shows
the cover art (assets/graphics/ui/cover.jpg, settings.COVER_IMAGE_PATH)
full-screen; pressing Enter fades out into the match-3 board
(PlayState). The "Guía" button next to the Enter prompt (or the G key)
opens the how-to-play guide (GuideState). Esc still quits from here -- that's handled unconditionally
at the Game level (see src/transmutacion_arcana.py), not by this state.
"""

import pygame

from gale.input_handler import InputData
from gale.state import BaseState, StateMachine
from gale.timer import Timer

import settings
from src import text as text_layer
from src.text import render_text

START_PROMPT = "Presiona Enter para jugar"
GUIDE_BUTTON_LABEL = "Guía (G)"
GUIDE_BUTTON_SIZE = (120, 40)
# Espacio entre el texto de Enter y el botón de la guía, que se dibujan
# juntos en una misma fila centrada al pie de la portada.
PROMPT_BUTTON_GAP = 20
PROMPT_ROW_CENTER_Y = settings.VIRTUAL_HEIGHT - 40


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

        prompt_width = settings.FONTS["small"].size(START_PROMPT)[0]
        button_width, button_height = GUIDE_BUTTON_SIZE
        row_left = (settings.VIRTUAL_WIDTH - (prompt_width + PROMPT_BUTTON_GAP + button_width)) // 2
        self.prompt_center_x = row_left + prompt_width // 2
        self.guide_button_rect = pygame.Rect(0, 0, button_width, button_height)
        self.guide_button_rect.midleft = (row_left + prompt_width + PROMPT_BUTTON_GAP, PROMPT_ROW_CENTER_Y)
        self.prompt_band = pygame.Surface((settings.VIRTUAL_WIDTH, button_height + 20), pygame.SRCALPHA)
        self.prompt_band.fill((10, 8, 16, 170))

    def render(self, surface: pygame.Surface) -> None:
        surface.blit(self.cover, (0, 0))

        # Franja semitransparente detrás de la fila de Enter + botón para
        # que se lea sobre cualquier zona de la portada.
        surface.blit(
            self.prompt_band,
            self.prompt_band.get_rect(center=(settings.VIRTUAL_WIDTH // 2, PROMPT_ROW_CENTER_Y)),
        )

        render_text(
            surface,
            START_PROMPT,
            settings.FONTS["small"],
            self.prompt_center_x,
            PROMPT_ROW_CENTER_Y,
            (235, 235, 240),
            center=True,
            shadowed=True,
        )

        # Mismo estilo que los botones de fin de partida (ver
        # PlayState._render_result_buttons).
        pygame.draw.rect(surface, (30, 24, 40), self.guide_button_rect, border_radius=8)
        pygame.draw.rect(surface, (255, 210, 80), self.guide_button_rect, width=3, border_radius=8)
        render_text(
            surface,
            GUIDE_BUTTON_LABEL,
            settings.FONTS["small"],
            self.guide_button_rect.centerx,
            self.guide_button_rect.centery,
            (235, 235, 240),
            center=True,
            shadowed=True,
        )

        pygame.draw.rect(
            self.screen_alpha_surface,
            (255, 255, 255, self.alpha_transition),
            pygame.Rect(0, 0, settings.VIRTUAL_WIDTH, settings.VIRTUAL_HEIGHT),
        )
        surface.blit(self.screen_alpha_surface, (0, 0))
        # Mismo fundido a blanco sobre el texto, que se dibuja aparte a
        # resolución de ventana (ver src/text.py).
        text_layer.overlay((255, 255, 255, self.alpha_transition))

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if not self.active or not input_data.pressed:
            return

        if input_id == "guide" or (input_id == "click" and self._is_guide_click(input_data.position)):
            self.state_machine.change("guide")
            return

        if input_id == "enter":
            self.active = False
            Timer.tween(
                0.5,
                [(self, {"alpha_transition": 255})],
                on_finish=lambda: self.state_machine.change("play"),
            )

    def _is_guide_click(self, position) -> bool:
        pos_x = position[0] * settings.VIRTUAL_WIDTH // settings.WINDOW_WIDTH
        pos_y = position[1] * settings.VIRTUAL_HEIGHT // settings.WINDOW_HEIGHT
        return self.guide_button_rect.collidepoint(pos_x, pos_y)
