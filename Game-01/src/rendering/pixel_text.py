"""
Drop-in replacement for gale.text.render_text matching this project's
retro arcade look (see assets/images/Cover.png): a solid fill color with
a clean black outline plus a pixelated gold drop shadow tucked under the
bottom-right edge, giving the beveled look a plain Press Start 2P render
doesn't have on its own. Same signature as gale.text.render_text, so
every caller only had to change its import, not the call itself.
"""
from typing import Optional

import pygame

_OUTLINE_COLOR = pygame.Color(0, 0, 0)
_BEVEL_SHADOW_COLOR = pygame.Color(184, 134, 11)  # dark gold, distinct from any accent fill
_BEVEL_OFFSET = 2

# One ring of 1px offsets around the glyph -- cheap and, at the tiny
# pixel-font sizes this game uses, indistinguishable from a true
# distance-field outline.
_OUTLINE_OFFSETS = ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1))


def render_text(
    surface: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    x: float,
    y: float,
    color: pygame.Color,
    bgcolor: Optional[pygame.Color] = None,
    center: bool = False,
    shadowed: bool = False,
) -> None:
    fill_surface = font.render(text, True, color, bgcolor)
    rect = fill_surface.get_rect()

    if center:
        rect.center = (x, y)
    else:
        rect.topleft = (x, y)

    if shadowed:
        bevel_surface = font.render(text, True, _BEVEL_SHADOW_COLOR)
        surface.blit(bevel_surface, (rect.x + _BEVEL_OFFSET, rect.y + _BEVEL_OFFSET))

        outline_surface = font.render(text, True, _OUTLINE_COLOR)
        for dx, dy in _OUTLINE_OFFSETS:
            surface.blit(outline_surface, (rect.x + dx, rect.y + dy))

    surface.blit(fill_surface, rect)
