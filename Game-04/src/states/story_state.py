"""
Intro screen: a short story presented as a terminal/console log, typed
out character by character. Any key or click either fast-forwards the
typing (if it's still going) or moves on to PlayState (once it's done).
"""
from typing import Any, List

import pygame

from gale.input_handler import InputData
from gale.state import BaseState

import settings

STORY_LINES: List[str] = [
    "CONEXIÓN ESTABLECIDA...",
    "TERMINAL DE INTERCEPCIÓN ACTIVA.",
    "",
    "Cada transmisión que llega debe ser verificada",
    "antes de que el sistema de seguridad la descarte.",
    "",
    "Tienes 4 SEGUNDOS por cada código.",
    "Si el temporizador llega a cero,",
    "el sistema se autodestruye.",
    "",
    "PRESIONA UNA TECLA O HAZ CLIC PARA COMENZAR",
]

CHARS_PER_SECOND = 45.0
_LEFT_MARGIN = 24
_LINE_HEIGHT = 22
_CURSOR_BLINK_HZ = 2.0
# +1 extra row so the blinking cursor (drawn one line below the last
# story line) is accounted for when centering the whole block.
_BLOCK_ROWS = len(STORY_LINES) + 1


class StoryState(BaseState):
    def enter(self, *args: Any, **kwargs: Any) -> None:
        self.elapsed = 0.0
        self.total_chars = sum(len(line) for line in STORY_LINES)
        settings.SOUNDS["intro"].play(loops=-1)

    def exit(self) -> None:
        settings.SOUNDS["intro"].stop()

    def _revealed_chars(self) -> int:
        return min(self.total_chars, int(self.elapsed * CHARS_PER_SECOND))

    def _fully_revealed(self) -> bool:
        return self._revealed_chars() >= self.total_chars

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if input_id not in ("mouse_click", "confirm") or not input_data.pressed:
            return

        if self._fully_revealed():
            self.state_machine.change("play")
        else:
            # Skip straight to the end of the typewriter effect instead
            # of jumping to the next screen outright, so the full story
            # is always at least visible for a moment.
            self.elapsed = self.total_chars / CHARS_PER_SECOND
            settings.SOUNDS["intro"].stop()

    def update(self, dt: float) -> None:
        was_fully_revealed = self._fully_revealed()
        self.elapsed += dt
        # The loop is only meant to underscore the letters typing
        # themselves out, so it cuts off the moment they finish -- not
        # only when the player leaves the screen (see exit() for that).
        if not was_fully_revealed and self._fully_revealed():
            settings.SOUNDS["intro"].stop()

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(settings.COLORS["console_background"])

        font = settings.FONTS["console"]
        color = settings.COLORS["console_text"]

        revealed = self._revealed_chars()
        consumed = 0
        # Centered vertically instead of pinned to the top, so the block
        # fills the canvas instead of leaving a big empty gap below it.
        y = (settings.VIRTUAL_HEIGHT - _BLOCK_ROWS * _LINE_HEIGHT) / 2

        for line in STORY_LINES:
            visible_len = max(0, min(len(line), revealed - consumed))
            consumed += len(line)

            if line:
                text = "> " + line[:visible_len]
                line_surface = font.render(text, True, color)
                surface.blit(line_surface, (_LEFT_MARGIN, y))

            y += _LINE_HEIGHT

        if self._fully_revealed() and int(self.elapsed * _CURSOR_BLINK_HZ) % 2 == 0:
            cursor_rect = pygame.Rect(_LEFT_MARGIN, y, 10, _LINE_HEIGHT - 6)
            pygame.draw.rect(surface, color, cursor_rect)
