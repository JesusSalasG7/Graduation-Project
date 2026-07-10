
from typing import Any
import sys

import pygame

from gale.input_handler import InputData
from gale.state import BaseState
from gale.text import render_text
from src.states import game_states

import settings

class FinalState(BaseState):
    """Victory screen shown after the boss is defeated."""

    def enter(self, level) -> None:
        self.level = level

        # Scale End.png to cover the full virtual screen (cropping the
        # overflow instead of letterboxing it) so it fills the space, the
        # same approach StartState uses for its background.
        original_width, original_height = settings.TEXTURES["End"].get_size()
        cover_scale = max(
            settings.VIRTUAL_WIDTH / original_width,
            settings.VIRTUAL_HEIGHT / original_height,
        )
        scaled_width = round(original_width * cover_scale)
        scaled_height = round(original_height * cover_scale)
        scaled_image = pygame.transform.smoothscale(
            settings.TEXTURES["End"], (scaled_width, scaled_height)
        )
        x = (scaled_width - settings.VIRTUAL_WIDTH) // 2
        y = (scaled_height - settings.VIRTUAL_HEIGHT) // 2
        self.background_image = scaled_image.subsurface(
            pygame.Rect(x, y, settings.VIRTUAL_WIDTH, settings.VIRTUAL_HEIGHT)
        ).copy()

        panel_width, panel_height = 300, 46
        self.panel_rect = pygame.Rect(0, 0, panel_width, panel_height)
        self.panel_rect.centerx = settings.VIRTUAL_WIDTH // 2
        self.panel_rect.y = settings.VIRTUAL_HEIGHT - panel_height - 12

        self.panel_surface = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
        pygame.draw.rect(
            self.panel_surface, (10, 10, 20, 170), pygame.Rect(0, 0, panel_width, panel_height)
        )

        button_width, button_height = 130, 22
        gap = 10
        buttons_y = self.panel_rect.y + (panel_height - button_height) // 2

        self.replay_button = pygame.Rect(
            self.panel_rect.centerx - gap // 2 - button_width, buttons_y, button_width, button_height
        )
        self.quit_button = pygame.Rect(
            self.panel_rect.centerx + gap // 2, buttons_y, button_width, button_height
        )

        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        pygame.mixer.music.load(settings.BASE_DIR / "assets" / "sounds" / "Final_music.mp3")
        pygame.mixer.music.play(loops=-1)

    def _to_virtual_position(self, position: Any) -> Any:
        scale_x = settings.WINDOW_WIDTH / settings.VIRTUAL_WIDTH
        scale_y = settings.WINDOW_HEIGHT / settings.VIRTUAL_HEIGHT
        return position[0] / scale_x, position[1] / scale_y

    def _replay(self) -> None:
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        self.state_machine.pop()
        self.state_machine.push(game_states.StartState(self.state_machine))

    def _quit(self) -> None:
        pygame.mixer.music.stop()
        pygame.quit()
        sys.exit()

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if input_id == "enter" and input_data.pressed:
            settings.SOUNDS["menu_click"].play()
            self._replay()
        elif input_id == "attack" and input_data.pressed:
            virtual_position = self._to_virtual_position(input_data.position)
            if self.replay_button.collidepoint(virtual_position):
                settings.SOUNDS["menu_click"].play()
                self._replay()
            elif self.quit_button.collidepoint(virtual_position):
                settings.SOUNDS["menu_click"].play()
                self._quit()

    def render(self, surface: pygame.Surface) -> None:
        surface.blit(self.background_image, (0, 0))
        surface.blit(self.panel_surface, self.panel_rect.topleft)
        self._render_button(surface, self.replay_button, "VOLVER A JUGAR")
        self._render_button(surface, self.quit_button, "SALIR DEL JUEGO")

    def _render_button(self, surface: pygame.Surface, rect: pygame.Rect, label: str) -> None:
        pygame.draw.rect(surface, (40, 40, 55), rect)
        pygame.draw.rect(surface, (231, 166, 45), rect, 1)
        render_text(
            surface,
            label,
            settings.FONTS["small"],
            rect.centerx,
            rect.centery,
            (230, 230, 230),
            center=True,
            shadowed=True,
        )
