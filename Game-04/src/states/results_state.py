"""
Final screen: total time taken, plus the round's words colored green
when the player got them right and red when they didn't -- no console
output, no detailed per-round breakdown on screen.
"""
from typing import Any, Dict, List, Optional

import pygame

from gale.input_handler import InputData
from gale.state import BaseState

import settings

RESULTS_TITLE = "RESULTADOS DE LA TRANSMISIÓN"
RESULTS_RESTART_HINT = "R = reiniciar transmisión      ESC = salir"

_GRID_COLUMNS = 2
_COLUMN_CENTERS = (settings.VIRTUAL_WIDTH * 0.3, settings.VIRTUAL_WIDTH * 0.7)
_TOTAL_TIME_TOP = 38
_ROW_TOP = 76
_ROW_SPACING = 42


class ResultsState(BaseState):
    def enter(
        self,
        game_log: Optional[List[Dict[str, Any]]] = None,
        correct_count: int = 0,
        wrong_count: int = 0,
        score: int = 0,
        total_time_ms: int = 0,
        **kwargs: Any,
    ) -> None:
        self.game_log = game_log or []
        self.correct_count = correct_count
        self.wrong_count = wrong_count
        self.score = score
        self.total_time_ms = total_time_ms
        settings.SOUNDS["victory"].play()

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if input_id == "restart" and input_data.pressed:
            self.state_machine.change("play")

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(settings.COLORS["background"])

        title_surface = settings.FONTS["results_title"].render(RESULTS_TITLE, True, settings.COLORS["accent"])
        surface.blit(title_surface, title_surface.get_rect(centerx=settings.VIRTUAL_WIDTH / 2, top=12))

        total_time_s = self.total_time_ms / 1000
        time_surface = settings.FONTS["stats"].render(f"TIEMPO TOTAL: {total_time_s:.1f}s", True, settings.COLORS["text"])
        surface.blit(time_surface, time_surface.get_rect(centerx=settings.VIRTUAL_WIDTH / 2, top=_TOTAL_TIME_TOP))

        for index, entry in enumerate(self.game_log):
            row, column = divmod(index, _GRID_COLUMNS)
            color = settings.COLORS["success"] if entry.get("is_correct") else settings.COLORS["error"]
            word_surface = settings.FONTS["stats"].render(entry["string"], True, color)
            surface.blit(
                word_surface,
                word_surface.get_rect(
                    centerx=_COLUMN_CENTERS[column],
                    top=_ROW_TOP + row * _ROW_SPACING,
                ),
            )

        hint_surface = settings.FONTS["hint"].render(RESULTS_RESTART_HINT, True, settings.COLORS["text_dim"])
        surface.blit(
            hint_surface, hint_surface.get_rect(centerx=settings.VIRTUAL_WIDTH / 2, bottom=settings.VIRTUAL_HEIGHT - 10)
        )
