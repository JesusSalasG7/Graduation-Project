"""
game_over_state.py

Pantalla final: victoria (2048 alcanzado) o derrota (sin movimientos).
"""
from __future__ import annotations

import pygame
from gale.state import BaseState

from src.rendering.drawing import draw_panel, draw_text_with_glow, space_background
from src.rendering.theme import (
    COLOR_LOSE,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    COLOR_TITLE_GLOW,
    COLOR_WIN,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)

class GameOverState(BaseState):
    """Pantalla final: victoria (2048 alcanzado) o derrota (sin movimientos)."""

    def enter(self, won: bool = False, score: int = 0, **kwargs) -> None:
        self.won = won
        self.score = score

        self.title_font = pygame.font.SysFont("arial", 62, bold=True)
        self.text_font = pygame.font.SysFont("arial", 30)
        self.help_font = pygame.font.SysFont("arial", 22)

    def exit(self) -> None:
        pass

    def on_input(self, input_id: str, input_data) -> None:
        if input_id == "restart" and getattr(input_data, "pressed", False):
            self.state_machine.change("play")

    def update(self, dt: float) -> None:
        pass

    def render(self, surface: pygame.Surface) -> None:
        surface.blit(space_background(*surface.get_size()), (0, 0))
        draw_panel(surface)

        title_color = COLOR_WIN if self.won else COLOR_LOSE
        title_text = "¡GANASTE!" if self.won else "GAME OVER"
        title = self.title_font.render(title_text, True, title_color)
        title_rect = title.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 80))

        draw_text_with_glow(
            surface, self.title_font, title_text, title_color, COLOR_TITLE_GLOW, title_rect.topleft
        )

        score_text = self.text_font.render(
            f"Puntuación final: {self.score}", True, COLOR_TEXT_PRIMARY
        )
        score_rect = score_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2))
        surface.blit(score_text, score_rect)

        help_text = self.help_font.render(
            "Presiona R para reiniciar   |   ESC para salir", True, COLOR_TEXT_MUTED
        )
        help_rect = help_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 65))
        surface.blit(help_text, help_rect)
