"""
Terminal-retro text renderer: a flat, monospaced glyph with an optional
soft neon glow behind it (a few faint same-color copies offset a couple
pixels in each direction), for a minimalist dark-terminal look.

Started as a straight copy of Game-01's pixel_text.py (matching its
drop-in signature for gale.text.render_text), but the two games'
visual identities have diverged since: Game-01 keeps its 8-bit arcade
outline + gold bevel, while TypeBeat's `shadowed` now renders a neon
halo in the text's own color instead of a black outline -- a better fit
for a solid near-black background where a black outline would just
disappear.
"""
from typing import Optional

import pygame

_GLOW_OFFSETS = ((-2, 0), (2, 0), (0, -2), (0, 2))
_GLOW_ALPHA = 60


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
        glow_surface = font.render(text, True, color)
        glow_surface.set_alpha(_GLOW_ALPHA)
        for dx, dy in _GLOW_OFFSETS:
            surface.blit(glow_surface, (rect.x + dx, rect.y + dy))

    surface.blit(fill_surface, rect)
