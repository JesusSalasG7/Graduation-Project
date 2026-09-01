"""
VictoryState: the popup/overlay shown on top of PlayState (via
ConwayGame.overlay_stack, a gale.state.StateStack) the moment a level's
win condition is met. The grid stays visible underneath a translucent
backdrop while this reads input exclusively.

Unlike the states registered in the main StateMachine, this one is
constructed and pushed directly by ConwayGame.show_victory rather than
built from a state_machine/name pair, so its constructor takes the
game reference instead of a StateMachine.
"""
from typing import Any, Dict, Tuple

import pygame

from gale.input_handler import InputData
from gale.text import render_text

import settings
from src.levels import LEVELS


class VictoryState:
    def __init__(self, game) -> None:
        self.game = game

    def enter(
        self,
        level_index: int,
        generation: int = 0,
        budget_used: int = 0,
        budget_total: int = 0,
        *args: Tuple[Any],
        **kwargs: Dict[str, Any],
    ) -> None:
        self.level_index = level_index
        self.level = LEVELS[level_index]
        self.generation = generation
        self.budget_used = budget_used
        self.budget_total = budget_total
        self.has_next_level = level_index + 1 < len(LEVELS)

    def exit(self) -> None:
        pass

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if not getattr(input_data, "pressed", False):
            return

        if input_id == "confirm":
            self.game.hide_overlay()
            if self.has_next_level:
                self.game.state_machine.change("play", level_index=self.level_index + 1)
            else:
                self.game.state_machine.change("start")
        elif input_id == "back":
            self.game.hide_overlay()
            self.game.state_machine.change("start")

    def update(self, dt: float) -> None:
        pass

    def render(self, surface: pygame.Surface) -> None:
        backdrop = pygame.Surface((settings.VIRTUAL_WIDTH, settings.VIRTUAL_HEIGHT), pygame.SRCALPHA)
        backdrop_color = settings.OVERLAY_BACKDROP_COLOR
        backdrop.fill((backdrop_color.r, backdrop_color.g, backdrop_color.b, 170))
        surface.blit(backdrop, (0, 0))

        center_x = settings.VIRTUAL_WIDTH // 2
        center_y = settings.VIRTUAL_HEIGHT // 2

        render_text(
            surface,
            "NIVEL COMPLETADO",
            settings.FONTS["banner"],
            center_x,
            center_y - 40,
            settings.WIN_BANNER_COLOR,
            center=True,
        )
        render_text(
            surface,
            f"{self.level.name}",
            settings.FONTS["menu"],
            center_x,
            center_y - 12,
            settings.HUD_TEXT_COLOR,
            center=True,
        )
        render_text(
            surface,
            f"Generaciones: {self.generation}   Presupuesto usado: {self.budget_used}/{self.budget_total}",
            settings.FONTS["hud"],
            center_x,
            center_y + 10,
            settings.HUD_TEXT_COLOR,
            center=True,
        )

        prompt = (
            "ENTER: siguiente nivel   ESC: menu"
            if self.has_next_level
            else "ENTER / ESC: volver al menu"
        )
        render_text(
            surface,
            prompt,
            settings.FONTS["hud"],
            center_x,
            center_y + 34,
            settings.HUD_ACCENT_COLOR,
            center=True,
        )
