"""
This file contains the class GameOverState: shown on defeat, on
beating a single foe's campaign slot, or on clearing the whole roster
(campaign victory).
"""

from typing import Any, Dict

import pygame

from gale.input_handler import InputData
from gale.state import BaseState
from gale.text import render_text

import settings
from src.combat.enemies import ENEMY_COUNT


class GameOverState(BaseState):
    def enter(self, **enter_params: Dict[str, Any]) -> None:
        self.victory = enter_params.get("victory", False)
        self.level = enter_params.get("level", 1)
        self.campaign_complete = self.victory and self.level >= ENEMY_COUNT

        self.text_alpha_surface = pygame.Surface((424, 176), pygame.SRCALPHA)
        pygame.draw.rect(
            self.text_alpha_surface, (30, 26, 40, 234), pygame.Rect(0, 0, 424, 176)
        )

    def render(self, surface: pygame.Surface) -> None:
        surface.blit(self.text_alpha_surface, (settings.VIRTUAL_WIDTH // 2 - 212, 160))

        if self.campaign_complete:
            title, color = "VICTORIA TOTAL", (255, 220, 120)
            subtitle = "Has purificado el reino con tu alquimia."
        elif self.victory:
            title, color = "COMBATE GANADO", (99, 255, 155)
            subtitle = f"Superaste el combate {self.level}."
        else:
            title, color = "DERROTA", (214, 64, 64)
            subtitle = f"Caiste en el combate {self.level}."

        render_text(
            surface,
            title,
            settings.FONTS["large"],
            settings.VIRTUAL_WIDTH // 2,
            200,
            color,
            center=True,
            shadowed=True,
        )
        render_text(
            surface,
            subtitle,
            settings.FONTS["medium"],
            settings.VIRTUAL_WIDTH // 2,
            250,
            (220, 220, 226),
            center=True,
            shadowed=True,
        )
        render_text(
            surface,
            "Presiona Enter",
            settings.FONTS["medium"],
            settings.VIRTUAL_WIDTH // 2,
            300,
            (200, 200, 210),
            center=True,
            shadowed=True,
        )

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if input_id == "enter" and input_data.pressed:
            self.state_machine.change("start")
