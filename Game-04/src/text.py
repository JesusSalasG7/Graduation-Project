"""
Crisp text on top of gale's virtual-resolution scaling.

gale renders every frame on a small VIRTUAL_WIDTH x VIRTUAL_HEIGHT
canvas and then upscales it to the window, which is fine for shapes but
turns small text into a blurry, blocky mess. Instead of blitting text on
that canvas, states call draw_text() with the same virtual coordinates
and anchors they'd pass to Surface.get_rect(): the text is queued and
MirrorCodeGame draws it straight onto the window, after the canvas has
been upscaled, with the same font rebuilt at window resolution (see
settings.FONT_SPECS). Layout is still computed with the virtual-size
font, so positions and sizes match what the canvas version looked like.
"""
from typing import Any, Dict, List, Tuple

import pygame

import settings

# Rect attributes that take a single x or y value; any other anchor
# (center, topleft, midbottom, ...) takes an (x, y) pair.
_X_ANCHORS = {"x", "left", "right", "centerx"}
_Y_ANCHORS = {"y", "top", "bottom", "centery"}

_queue: List[Tuple[str, str, Any, Dict[str, Any]]] = []
_window_fonts: Dict[Tuple[str, int], pygame.font.Font] = {}


def draw_text(surface: pygame.Surface, font_key: str, text: str, color: Any, **anchor: Any) -> pygame.Rect:
    """Queues `text` to be drawn at window resolution, positioned by
    `anchor` in virtual coordinates (e.g. centerx=..., top=...), and
    returns the rect it occupies on the virtual canvas. `surface` is the
    virtual canvas the caller is rendering on -- unused, kept so call
    sites read like a regular blit."""
    rect = pygame.Rect((0, 0), settings.FONTS[font_key].size(text))
    for name, value in anchor.items():
        setattr(rect, name, value)
    _queue.append((font_key, text, color, anchor))
    return rect


def begin_frame() -> None:
    """Drops text queued by anything that rendered outside the game loop
    (tests driving a state's render() directly, for instance)."""
    _queue.clear()


def flush(window: pygame.Surface, scale_x: float, scale_y: float) -> None:
    """Draws every queued text onto `window`, mapping virtual
    coordinates with the given scale, and empties the queue."""
    font_scale = min(scale_x, scale_y)
    for font_key, text, color, anchor in _queue:
        text_surface = _window_font(font_key, font_scale).render(text, True, color)
        rect = text_surface.get_rect()
        for name, value in anchor.items():
            if name in _X_ANCHORS:
                value = round(value * scale_x)
            elif name in _Y_ANCHORS:
                value = round(value * scale_y)
            else:
                value = (round(value[0] * scale_x), round(value[1] * scale_y))
            setattr(rect, name, value)
        window.blit(text_surface, rect)
    _queue.clear()


def _window_font(font_key: str, scale: float) -> pygame.font.Font:
    family, size, bold = settings.FONT_SPECS[font_key]
    scaled_size = max(1, round(size * scale))
    cache_key = (font_key, scaled_size)
    if cache_key not in _window_fonts:
        _window_fonts[cache_key] = settings.load_font(family, scaled_size, bold)
    return _window_fonts[cache_key]
