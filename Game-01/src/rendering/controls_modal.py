"""
"How to play" modal: the arrow-key cluster plus, below it, a line of
text that types itself out describing what each arrow does -- cycling
through the four keys automatically. Purely pixel art and text over
whatever is already on the surface -- no panel/background of its own --
so it reads as a floating overlay rather than a boxed dialog.
"""
from typing import Dict, Tuple

import pygame

from gale.text import render_text

import settings

_DIRECTIONS = ("up", "right", "down", "left")

_MOVEMENT_TEXT = {
    "up": "Flecha arriba: sube",
    "right": "Flecha derecha: va a la derecha",
    "down": "Flecha abajo: baja",
    "left": "Flecha izquierda: va a la izquierda",
}

# How long the highlight lingers on each key before moving to the next
# one, and how long it takes the movement line to finish typing itself
# out after switching keys.
_HOLD_SECONDS = 1.4
_TYPE_SECONDS = 0.6

_ROW_SPACING = 44  # center-to-center distance from "down" out to "left"/"right"

# Center-to-center distance from "down" up to "up". Deliberately larger
# than _ROW_SPACING so the highlight ring around "up" never overlaps the
# "down" keycap sitting right below it.
_UP_SPACING = 72

_HEADER_OFFSET = -144
_TEXT_OFFSET = 40  # below the key cluster
_FOOTER_OFFSET = 150

_HIGHLIGHT_COLOR = pygame.Color(255, 235, 59)
_HIGHLIGHT_PADDING = 6


class ControlsModal:
    def __init__(self, center_x: float, center_y: float) -> None:
        self.center_x = center_x
        self.center_y = center_y
        self._direction_index = 0
        self._timer = 0.0

    def update(self, dt: float) -> None:
        self._timer += dt

        if self._timer >= _HOLD_SECONDS:
            self._timer -= _HOLD_SECONDS
            self._direction_index = (self._direction_index + 1) % len(_DIRECTIONS)

    def render(self, surface: pygame.Surface) -> None:
        render_text(
            surface,
            "Controles de juego",
            settings.FONTS["hud"],
            self.center_x,
            self.center_y + _HEADER_OFFSET,
            settings.UI_TEXT_COLOR,
            center=True,
            shadowed=True,
        )

        key_positions = self._key_positions()
        direction = _DIRECTIONS[self._direction_index]

        self._render_highlight(surface, key_positions[direction])

        for key_direction, position in key_positions.items():
            sprite = settings.SPRITES[f"key_{key_direction}"]
            surface.blit(sprite, sprite.get_rect(center=position))

        self._render_movement_text(surface, direction)

        render_text(
            surface,
            "Presiona ENTER para jugar",
            settings.FONTS["hud"],
            self.center_x,
            self.center_y + _FOOTER_OFFSET,
            settings.UI_ACCENT_COLOR,
            center=True,
            shadowed=True,
        )

    def _key_positions(self) -> Dict[str, Tuple[float, float]]:
        cx, cy = self.center_x, self.center_y
        return {
            "up": (cx, cy - _UP_SPACING),
            "left": (cx - _ROW_SPACING, cy),
            "down": (cx, cy),
            "right": (cx + _ROW_SPACING, cy),
        }

    def _render_highlight(self, surface: pygame.Surface, position: Tuple[float, float]) -> None:
        size = settings.SPRITES["key_up"].get_size()
        rect = pygame.Rect(0, 0, size[0] + _HIGHLIGHT_PADDING, size[1] + _HIGHLIGHT_PADDING)
        rect.center = position
        pygame.draw.rect(surface, _HIGHLIGHT_COLOR, rect, width=3, border_radius=6)

    def _render_movement_text(self, surface: pygame.Surface, direction: str) -> None:
        # Typewriter reveal: the fraction of the line shown grows with
        # how long the current key has been highlighted, so the text
        # finishes typing itself out shortly after the highlight lands
        # and then just sits there for the rest of the hold.
        full_text = _MOVEMENT_TEXT[direction]
        reveal_ratio = min(1.0, self._timer / _TYPE_SECONDS)
        visible_chars = int(len(full_text) * reveal_ratio)

        render_text(
            surface,
            full_text[:visible_chars],
            settings.FONTS["hud"],
            self.center_x,
            self.center_y + _TEXT_OFFSET,
            settings.UI_TEXT_COLOR,
            center=True,
            shadowed=True,
        )
