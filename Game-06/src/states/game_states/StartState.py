
from typing import Any

import pygame

from gale.input_handler import InputData
from gale.state import BaseState
from gale.text import render_text
from src.mixins import FadeMixin
from src.states import game_states

import settings

class StartState(BaseState, FadeMixin):
    def enter(self) -> None:
        self.render_text = True
        self.init_fade(settings.VIRTUAL_WIDTH, settings.VIRTUAL_HEIGHT)

        # Translucent panel behind the menu buttons so they stay readable
        # over the busy pixel-art background.
        panel_width, panel_height = 280, 46
        self.panel_rect = pygame.Rect(0, 0, panel_width, panel_height)
        self.panel_rect.centerx = settings.VIRTUAL_WIDTH // 2
        self.panel_rect.y = settings.VIRTUAL_HEIGHT - panel_height - 12

        self.panel_surface = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
        pygame.draw.rect(
            self.panel_surface, (10, 10, 20, 170), pygame.Rect(0, 0, panel_width, panel_height)
        )

        button_width, button_height = 120, 22
        gap = 10
        buttons_y = self.panel_rect.y + (panel_height - button_height) // 2

        self.instructions_button = pygame.Rect(
            self.panel_rect.centerx - gap // 2 - button_width, buttons_y, button_width, button_height
        )
        self.start_button = pygame.Rect(
            self.panel_rect.centerx + gap // 2, buttons_y, button_width, button_height
        )

        self.active = True

        # Scale the background so it always covers the full virtual screen
        # (cropping the overflow instead of letterboxing it), then cache the
        # result since the source texture never changes.
        original_width, original_height = settings.TEXTURES["background"].get_size()
        scale_width = settings.VIRTUAL_WIDTH / original_width
        scale_height = settings.VIRTUAL_HEIGHT / original_height
        cover_scale = max(scale_width, scale_height)

        scaled_width = round(original_width * cover_scale)
        scaled_height = round(original_height * cover_scale)
        scaled_background = pygame.transform.smoothscale(
            settings.TEXTURES["background"], (scaled_width, scaled_height)
        )

        x = (scaled_width - settings.VIRTUAL_WIDTH) // 2
        y = (scaled_height - settings.VIRTUAL_HEIGHT) // 2
        self.background_image = scaled_background.subsurface(
            pygame.Rect(x, y, settings.VIRTUAL_WIDTH, settings.VIRTUAL_HEIGHT)
        ).copy()

        pygame.mixer.music.load(settings.BASE_DIR / "assets" / "sounds" / "Music_start.mp3")
        pygame.mixer.music.play(loops=-1)

    def render(self, surface: pygame.Surface) -> None:
        self.surface = surface
        surface.blit(self.background_image, (0, 0))

        if self.render_text:
            surface.blit(self.panel_surface, self.panel_rect.topleft)
            self._render_button(surface, self.instructions_button, "INSTRUCCIONES")
            self._render_button(surface, self.start_button, "COMENZAR")

        self.render_fade(surface)

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

    def _to_virtual_position(self, position: Any) -> Any:
        scale_x = settings.WINDOW_WIDTH / settings.VIRTUAL_WIDTH
        scale_y = settings.WINDOW_HEIGHT / settings.VIRTUAL_HEIGHT
        return position[0] / scale_x, position[1] / scale_y

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if not self.active:
            return

        if input_id == "enter" and input_data.pressed:
            settings.SOUNDS["menu_click"].play()
            self._begin_start()
        elif input_id == "attack" and input_data.pressed and hasattr(input_data, "position"):
            # "attack" is also bound to the space bar (see settings.py), whose
            # KeyboardData has no "position" attribute; only mouse clicks
            # carry one, so only those can hit a menu button.
            virtual_position = self._to_virtual_position(input_data.position)
            if self.start_button.collidepoint(virtual_position):
                settings.SOUNDS["menu_click"].play()
                self._begin_start()
            elif self.instructions_button.collidepoint(virtual_position):
                settings.SOUNDS["menu_click"].play()
                self.render_text = False
                self.state_machine.push(
                    game_states.InstructionsState(self.state_machine), start_state=self
                )

    def _begin_start(self) -> None:
        self.active = False
        self.render_text = False
        self.start_fade_out(1, on_finish=self.start_game)

    def start_game(self) -> None:
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        self.state_machine.pop()
        self.state_machine.push(game_states.PlayState(self.state_machine), level=2)