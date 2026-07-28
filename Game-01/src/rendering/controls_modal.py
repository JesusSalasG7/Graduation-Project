"""
"How to play" modal: the arrow-key cluster plus a small animated hand
that cycles through pressing each key, framed by two lines of
instructional text. Purely pixel art and text over whatever is already
on the surface -- no panel/background of its own -- so it reads as a
floating overlay rather than a boxed dialog.
"""
import math
from typing import Dict, Tuple

import pygame

from gale.text import render_text

import settings

_DIRECTIONS = ("up", "right", "down", "left")

# How long the hand lingers pointing at each key before moving to the
# next one, and how long the little downward "press" dip at the start
# of each hold takes.
_HOLD_SECONDS = 0.8
_PRESS_SECONDS = 0.18
_PRESS_DIP = 6

_ROW_SPACING = 44  # center-to-center distance from "down" out to "left"/"right"

# Center-to-center distance from "down" up to "up". Deliberately much
# larger than _ROW_SPACING: the hovering hand needs its full sprite
# height of clearance above whichever key is active, and when that key
# is "down", the "up" key sitting right above it is what it has to clear
# -- too tight a gap here and the hand overlaps the "up" keycap instead
# of reading as pointing at "down" (see _render_hand).
_UP_SPACING = 72

_HEADER_OFFSET = -144
_FOOTER_OFFSET = 150


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
            pygame.Color("white"),
            center=True,
            shadowed=True,
        )

        key_positions = self._key_positions()

        for direction, position in key_positions.items():
            sprite = settings.SPRITES[f"key_{direction}"]
            surface.blit(sprite, sprite.get_rect(center=position))

        self._render_hand(surface, key_positions)

        render_text(
            surface,
            "Presiona ENTER para jugar",
            settings.FONTS["hud"],
            self.center_x,
            self.center_y + _FOOTER_OFFSET,
            pygame.Color("yellow"),
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

    def _render_hand(self, surface: pygame.Surface, key_positions: Dict[str, Tuple[float, float]]) -> None:
        direction = _DIRECTIONS[self._direction_index]
        key_x, key_y = key_positions[direction]

        # A quick downward-then-back dip right after switching keys reads
        # as the hand pressing the newly-highlighted one.
        if self._timer < _PRESS_SECONDS:
            dip = math.sin((self._timer / _PRESS_SECONDS) * math.pi) * _PRESS_DIP
        else:
            dip = 0.0

        hand = settings.SPRITES["hand"]
        key_half_height = settings.SPRITES[f"key_{direction}"].get_height() / 2
        # Rests with its fingertip just touching the key's top edge, dips
        # further onto the key face for the press.
        fingertip_y = key_y - key_half_height * 0.6 + dip
        surface.blit(hand, hand.get_rect(midbottom=(key_x, fingertip_y)))
