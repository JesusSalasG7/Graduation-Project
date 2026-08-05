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
from src.rendering.pixel_text import render_text

import settings
from src import records

_OPTIONS = (
    ("classic", "Modo Clasico"),
    ("challenge", "Modo Desafio"),
    ("clear_records", "Borrar Records"),
)

# Shown instead of the main list once "Borrar Records" is confirmed, so
# an accidental ENTER on that option can't wipe the leaderboard outright
# -- navigated/confirmed the same way as the main options. "cancel" is
# listed second and is the default selection (see enter()).
_CONFIRM_CLEAR_OPTIONS = ("confirm", "cancel")
_CONFIRM_CLEAR_LABELS = ("Si, borrar", "Cancelar")

# Center-to-center vertical distance between consecutive lines in the
# options list and the clear-records confirmation, both centered as a
# block around the middle of the screen (see _render_options/
# _render_confirm_clear).
_LINE_SPACING = 24


class MenuState(BaseState):
    def enter(self, *args: Tuple[Any], **kwargs: Dict[str, Any]) -> None:
        self._selected = 0
        self._confirming_clear = False
        self._confirm_clear_selected = 1

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if not input_data.pressed:
            return

        if self._confirming_clear:
            self._handle_confirm_clear_input(input_id)
            return

        if input_id == "move_up":
            self._selected = (self._selected - 1) % len(_OPTIONS)
        elif input_id == "move_down":
            self._selected = (self._selected + 1) % len(_OPTIONS)
        elif input_id == "restart":
            mode, _ = _OPTIONS[self._selected]

            if mode == "clear_records":
                self._confirm_clear_selected = 1
                self._confirming_clear = True
            else:
                self.state_machine.change("play", mode=mode)

    def _handle_confirm_clear_input(self, input_id: str) -> None:
        if input_id in ("move_up", "move_down"):
            self._confirm_clear_selected = 1 - self._confirm_clear_selected
        elif input_id == "restart":
            if _CONFIRM_CLEAR_OPTIONS[self._confirm_clear_selected] == "confirm":
                records.clear()

            self._confirming_clear = False

    def render(self, surface: pygame.Surface) -> None:
        surface.blit(settings.SPRITES["map"], (0, 0))

        self._render_leaderboard(surface)

        center_x = settings.VIRTUAL_WIDTH // 2
        center_y = settings.VIRTUAL_HEIGHT // 2

        if self._confirming_clear:
            self._render_confirm_clear(surface, center_x, center_y)
        else:
            self._render_options(surface, center_x, center_y)

        render_text(
            surface,
            "Flechas arriba/abajo para elegir, ENTER para confirmar",
            settings.FONTS["hud"],
            center_x,
            settings.VIRTUAL_HEIGHT - 20,
            settings.UI_TEXT_COLOR,
            center=True,
            shadowed=True,
        )

    def _render_options(self, surface: pygame.Surface, center_x: int, center_y: int) -> None:
        # Centered as a block around center_y rather than hanging off
        # where the title used to sit, now that there is no title.
        middle = (len(_OPTIONS) - 1) / 2

        for i, (_, label) in enumerate(_OPTIONS):
            selected = i == self._selected
            color = settings.UI_ACCENT_COLOR if selected else settings.UI_TEXT_COLOR
            prefix = "> " if selected else "  "
            render_text(
                surface,
                prefix + label,
                settings.FONTS["menu"],
                center_x,
                center_y + (i - middle) * _LINE_SPACING,
                color,
                center=True,
                shadowed=True,
            )

    def _render_confirm_clear(self, surface: pygame.Surface, center_x: int, center_y: int) -> None:
        render_text(
            surface,
            "Borrar todos los records? No se puede deshacer",
            settings.FONTS["hud"],
            center_x,
            center_y - _LINE_SPACING,
            settings.UI_ACCENT_COLOR,
            center=True,
            shadowed=True,
        )

        for i, label in enumerate(_CONFIRM_CLEAR_LABELS):
            selected = i == self._confirm_clear_selected
            color = settings.UI_ACCENT_COLOR if selected else settings.UI_TEXT_COLOR
            prefix = "> " if selected else "  "
            render_text(
                surface,
                prefix + label,
                settings.FONTS["menu"],
                center_x,
                center_y + i * _LINE_SPACING,
                color,
                center=True,
                shadowed=True,
            )

    def _render_leaderboard(self, surface: pygame.Surface) -> None:
        """
        Top-left panel listing every saved record (name + score), best
        first -- populated from PlayState's new-record name prompt (see
        src/records.py).
        """
        x, y = 10, 8
        line_height = 16

        render_text(
            surface,
            "RECORDS",
            settings.FONTS["hud"],
            x,
            y,
            settings.UI_ACCENT_COLOR,
            shadowed=True,
        )

        entries = records.load_all()

        if not entries:
            render_text(
                surface,
                "Sin registros aun",
                settings.FONTS["hud"],
                x,
                y + line_height,
                settings.UI_TEXT_COLOR,
                shadowed=True,
            )
            return

        for i, entry in enumerate(entries):
            color = settings.UI_ACCENT_COLOR if i == 0 else settings.UI_TEXT_COLOR
            render_text(
                surface,
                f"{i + 1}. {entry['name']} - {entry['score']}",
                settings.FONTS["hud"],
                x,
                y + line_height * (i + 1),
                color,
                shadowed=True,
            )
