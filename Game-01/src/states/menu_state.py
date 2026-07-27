"""
Start screen: lets the player pick a ruleset before PlayState builds the
World. Options map 1:1 to World's `mode` argument, so this state's only
job is to forward "classic"/"challenge" through state_machine.change --
it owns no game rules itself.
"""
from typing import Any, Dict, Tuple

import pygame

from gale.input_handler import InputData
from gale.state import BaseState
from gale.text import render_text

import settings

_OPTIONS = (
    ("classic", "Modo Clasico"),
    ("challenge", "Modo Desafio"),
)


class MenuState(BaseState):
    def enter(self, *args: Tuple[Any], **kwargs: Dict[str, Any]) -> None:
        self._selected = 0

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if not input_data.pressed:
            return

        if input_id == "move_up":
            self._selected = (self._selected - 1) % len(_OPTIONS)
        elif input_id == "move_down":
            self._selected = (self._selected + 1) % len(_OPTIONS)
        elif input_id == "restart":
            mode, _ = _OPTIONS[self._selected]
            self.state_machine.change("play", mode=mode)

    def render(self, surface: pygame.Surface) -> None:
        surface.blit(settings.SPRITES["map"], (0, 0))

        center_x = settings.VIRTUAL_WIDTH // 2
        title_y = settings.VIRTUAL_HEIGHT // 2 - 46

        render_text(
            surface,
            "SNAKE",
            settings.FONTS["title"],
            center_x,
            title_y,
            pygame.Color("white"),
            center=True,
            shadowed=True,
        )

        for i, (_, label) in enumerate(_OPTIONS):
            selected = i == self._selected
            color = pygame.Color("yellow") if selected else pygame.Color("white")
            prefix = "> " if selected else "  "
            render_text(
                surface,
                prefix + label,
                settings.FONTS["hud"],
                center_x,
                title_y + 40 + i * 24,
                color,
                center=True,
                shadowed=True,
            )

        render_text(
            surface,
            "Flechas arriba/abajo para elegir, ENTER para confirmar",
            settings.FONTS["hud"],
            center_x,
            settings.VIRTUAL_HEIGHT - 20,
            pygame.Color("white"),
            center=True,
            shadowed=True,
        )
