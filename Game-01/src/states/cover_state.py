"""
Title/cover screen: the first thing the player sees, before the mode
menu. Purely a splash for assets/images/Cover.png (see
settings.SPRITES["cover"]) -- owns no game rules, just waits for the
player to dismiss it.
"""
from typing import Any, Dict, Tuple

import pygame

from gale.input_handler import InputData
from gale.state import BaseState

from src.rendering.pixel_text import render_text

import settings


class CoverState(BaseState):
    def on_input(self, input_id: str, input_data: InputData) -> None:
        if input_data.pressed and input_id == "restart":
            self.state_machine.change("menu")

    def render(self, surface: pygame.Surface) -> None:
        surface.blit(settings.SPRITES["cover"], (0, 0))

        render_text(
            surface,
            "Presiona ENTER para continuar",
            settings.FONTS["hud"],
            settings.VIRTUAL_WIDTH // 2,
            settings.VIRTUAL_HEIGHT - 20,
            settings.UI_TEXT_COLOR,
            center=True,
            shadowed=True,
        )
