"""
StartState: title screen and level selection. Navigate with UP/DOWN,
ENTER to play the highlighted level, ESC to quit.
"""
from typing import Any, Dict, Tuple

import pygame

from gale.input_handler import InputData
from gale.state import BaseState
from gale.text import render_text

import settings
from src.levels import LEVELS


class StartState(BaseState):
    def __init__(self, state_machine, game) -> None:
        super().__init__(state_machine)
        self.game = game
        self.selected_index = 0

    def enter(self, *args: Tuple[Any], **kwargs: Dict[str, Any]) -> None:
        self.selected_index = 0

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if not getattr(input_data, "pressed", False):
            return

        if input_id == "nav_up":
            self.selected_index = (self.selected_index - 1) % len(LEVELS)
        elif input_id == "nav_down":
            self.selected_index = (self.selected_index + 1) % len(LEVELS)
        elif input_id == "confirm":
            self.state_machine.change("play", level_index=self.selected_index)
        elif input_id == "back":
            self.game.quit()

    def update(self, dt: float) -> None:
        pass

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(settings.BACKGROUND_COLOR)

        render_text(
            surface,
            "CONWAY'S PUZZLE",
            settings.FONTS["title"],
            settings.VIRTUAL_WIDTH // 2,
            50,
            settings.HUD_ACCENT_COLOR,
            center=True,
        )

        y = 120
        for index, level in enumerate(LEVELS):
            selected = index == self.selected_index
            color = settings.MENU_HIGHLIGHT_COLOR if selected else settings.HUD_TEXT_COLOR
            prefix = "> " if selected else "  "
            render_text(
                surface,
                f"{prefix}{index + 1}. {level.name}",
                settings.FONTS["menu"],
                settings.VIRTUAL_WIDTH // 2,
                y,
                color,
                center=True,
            )
            if selected:
                render_text(
                    surface,
                    level.description,
                    settings.FONTS["hud"],
                    settings.VIRTUAL_WIDTH // 2,
                    y + 18,
                    settings.HUD_TEXT_COLOR,
                    center=True,
                )
            y += 46

        render_text(
            surface,
            "Flechas: navegar   ENTER: jugar   ESC: salir",
            settings.FONTS["hud"],
            settings.VIRTUAL_WIDTH // 2,
            settings.VIRTUAL_HEIGHT - 20,
            settings.HUD_TEXT_COLOR,
            center=True,
        )
