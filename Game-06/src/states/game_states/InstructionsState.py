
import pygame

from gale.input_handler import InputData
from gale.state import BaseState
from gale.text import render_text

import settings


class InstructionsState(BaseState):
    def enter(self, start_state=None) -> None:
        self.start_state = start_state
        panel_width, panel_height = settings.VIRTUAL_WIDTH - 40, settings.VIRTUAL_HEIGHT - 30
        self.panel_rect = pygame.Rect(0, 0, panel_width, panel_height)
        self.panel_rect.center = (settings.VIRTUAL_WIDTH // 2, settings.VIRTUAL_HEIGHT // 2)

        self.panel_surface = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
        pygame.draw.rect(
            self.panel_surface, (10, 10, 20, 210), pygame.Rect(0, 0, panel_width, panel_height)
        )

        self.lines = [
            "FLECHAS IZQ/DER: moverse",
            "FLECHA ARRIBA: saltar",
            "ESPACIO o CLIC IZQUIERDO: atacar",
            "(podes atacar tambien en el aire)",
            "P: pausar el juego",
            "",
            "Rescata a la princesa atravesando",
            "cada nivel y derrota al jefe final.",
        ]

        self.back_button = pygame.Rect(0, 0, 110, 18)
        self.back_button.centerx = settings.VIRTUAL_WIDTH // 2
        self.back_button.bottom = self.panel_rect.bottom - 8

    def _to_virtual_position(self, position):
        scale_x = settings.WINDOW_WIDTH / settings.VIRTUAL_WIDTH
        scale_y = settings.WINDOW_HEIGHT / settings.VIRTUAL_HEIGHT
        return position[0] / scale_x, position[1] / scale_y

    def _go_back(self) -> None:
        settings.SOUNDS["menu_click"].play()
        if self.start_state is not None:
            self.start_state.render_text = True
        self.state_machine.pop()

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if input_id == "enter" and input_data.pressed:
            self._go_back()
        elif input_id == "attack" and input_data.pressed and hasattr(input_data, "position"):
            # "attack" is also bound to the space bar (see settings.py), whose
            # KeyboardData has no "position" attribute; only mouse clicks
            # carry one, so only those can hit the back button.
            if self.back_button.collidepoint(self._to_virtual_position(input_data.position)):
                self._go_back()

    def render(self, surface: pygame.Surface) -> None:
        surface.blit(self.panel_surface, self.panel_rect.topleft)

        render_text(
            surface,
            "INSTRUCCIONES",
            settings.FONTS["medium"],
            settings.VIRTUAL_WIDTH // 2,
            self.panel_rect.y + 16,
            (231, 166, 45),
            center=True,
            shadowed=True,
        )

        for i, line in enumerate(self.lines):
            render_text(
                surface,
                line,
                settings.FONTS["small"],
                settings.VIRTUAL_WIDTH // 2,
                self.panel_rect.y + 38 + i * 12,
                (230, 230, 230),
                center=True,
                shadowed=True,
            )

        pygame.draw.rect(surface, (40, 40, 55), self.back_button)
        pygame.draw.rect(surface, (231, 166, 45), self.back_button, 1)
        render_text(
            surface,
            "VOLVER (ENTER)",
            settings.FONTS["small"],
            self.back_button.centerx,
            self.back_button.centery,
            (230, 230, 230),
            center=True,
            shadowed=True,
        )
