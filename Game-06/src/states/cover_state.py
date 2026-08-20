"""
Title/cover screen: the first (and only non-gameplay) thing the player
sees. ENTER drops straight into PlayState at settings.DEFAULT_DIFFICULTY
-- there is no separate difficulty-select menu -- so this also carries
the leaderboard, which used to live on that now-removed screen.
"""
import pygame

from gale.input_handler import InputData
from gale.state import BaseState

from src.rendering.pixel_text import render_text

import settings
from src import records


class CoverState(BaseState):
    def on_input(self, input_id: str, input_data: InputData) -> None:
        if input_data.pressed and input_id == "restart":
            self.state_machine.change("play", difficulty=settings.DEFAULT_DIFFICULTY)

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(settings.BACKGROUND_COLOR)

        center_x = settings.VIRTUAL_WIDTH // 2
        center_y = settings.VIRTUAL_HEIGHT // 2

        render_text(
            surface,
            "TYPEBEAT",
            settings.FONTS["title"],
            center_x,
            center_y - 40,
            settings.UI_ACCENT_COLOR,
            center=True,
            shadowed=True,
        )
        render_text(
            surface,
            "Mecanografia al ritmo",
            settings.FONTS["hud"],
            center_x,
            center_y - 4,
            settings.UI_TEXT_COLOR,
            center=True,
            shadowed=True,
        )
        render_text(
            surface,
            "Presiona ENTER para jugar",
            settings.FONTS["hud"],
            center_x,
            settings.VIRTUAL_HEIGHT - 20,
            settings.UI_ACCENT_COLOR,
            center=True,
            shadowed=True,
        )

        self._render_leaderboard(surface)

    def _render_leaderboard(self, surface: pygame.Surface) -> None:
        x, y = 10, 8
        line_height = 16

        render_text(
            surface, "RECORDS", settings.FONTS["hud"], x, y, settings.UI_ACCENT_COLOR, shadowed=True
        )

        entries = records.leaderboard()

        if not entries:
            render_text(
                surface,
                "Sin registros aun",
                settings.FONTS["hud"],
                x,
                y + line_height,
                settings.UI_MUTED_COLOR,
            )
            return

        for i, entry in enumerate(entries):
            color = settings.UI_ACCENT_COLOR if i == 0 else settings.UI_TEXT_COLOR
            line = f"{i + 1}. {entry['name']} - {entry['score']}"

            # None whenever that run's sort_task wasn't implemented (see
            # PlayState._save_record) -- nothing to report then, so the
            # line just falls back to name/score like before this field
            # existed.
            if entry["sort_time"] is not None:
                line += f" ({entry['sort_time'] * 1000:.3f} ms)"

            render_text(
                surface,
                line,
                settings.FONTS["hud"],
                x,
                y + line_height * (i + 1),
                color,
            )
