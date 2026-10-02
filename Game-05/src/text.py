"""
Crisp text on top of gale's virtual-resolution scaling.

gale renders every frame on the VIRTUAL_WIDTH x VIRTUAL_HEIGHT canvas
and then upscales it to the window, which blurs text. render_text()
below is a drop-in replacement for gale.text.render_text (same
arguments, same virtual coordinates): instead of blitting onto the
canvas it queues the text, and ArcaneTransmutationGame draws the queue
straight onto the window after the canvas has been upscaled, with the
same font rebuilt at window resolution (see settings.FONT_SIZES).

Since queued text ends up above everything on the canvas, a state that
covers the screen with a translucent layer AFTER drawing some text
(PlayState's end-of-match overlay, StartState's fade to white) must
also call overlay() with the same color, so the text drawn before it
gets covered the same way the canvas does.
"""
from typing import Any, Dict, List, Optional, Tuple

import pygame

import settings

_queue: List[Tuple[str, Any]] = []
_window_fonts: Dict[Tuple[str, int], pygame.font.Font] = {}
_font_keys: Dict[int, str] = {id(font): key for key, font in settings.FONTS.items()}


def render_text(
    surface: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    x: float,
    y: float,
    color: Any,
    bgcolor: Optional[Any] = None,
    center: bool = False,
    shadowed: bool = False,
) -> None:
    """Same signature as gale.text.render_text. `font` must be one of
    settings.FONTS; `surface` is unused (the text is drawn onto the
    window later, see flush)."""
    _queue.append(("text", (_font_keys[id(font)], text, x, y, color, bgcolor, center, shadowed)))


def overlay(color: Tuple[int, int, int, int]) -> None:
    """Covers every text queued so far with a full-screen `color`
    (RGBA) layer, matching a translucent fill the caller just blitted
    over the whole virtual canvas."""
    _queue.append(("overlay", color))


def begin_frame() -> None:
    """Drops anything queued outside the game loop (e.g. by a test
    calling a state's render() directly)."""
    _queue.clear()


def flush(window: pygame.Surface, scale_x: float, scale_y: float) -> None:
    """Draws the queued text onto `window`, mapping virtual coordinates
    with the given scale, and empties the queue."""
    if not _queue:
        return

    layer = pygame.Surface(window.get_size(), pygame.SRCALPHA)
    font_scale = min(scale_x, scale_y)
    shadow_offset = max(1, round(font_scale))

    for kind, payload in _queue:
        if kind == "overlay":
            # Exact "color over text" compositing, applied only to the
            # RGB of pixels already on the layer (alpha untouched, so
            # empty areas stay transparent): rgb * (1 - a) + color * a.
            r, g, b, a = payload
            keep = 255 - a
            layer.fill((keep, keep, keep), special_flags=pygame.BLEND_RGB_MULT)
            layer.fill((r * a // 255, g * a // 255, b * a // 255), special_flags=pygame.BLEND_RGB_ADD)
            continue

        font_key, text, x, y, color, bgcolor, center, shadowed = payload
        font = _window_font(font_key, font_scale)
        text_surface = font.render(text, True, color, bgcolor)
        rect = text_surface.get_rect()
        if center:
            rect.center = (round(x * scale_x), round(y * scale_y))
        else:
            rect.topleft = (round(x * scale_x), round(y * scale_y))

        if shadowed:
            shadow_surface = font.render(text, True, (0, 0, 0))
            layer.blit(shadow_surface, rect.move(shadow_offset, shadow_offset))
        layer.blit(text_surface, rect)

    window.blit(layer, (0, 0))
    _queue.clear()


def _window_font(font_key: str, scale: float) -> pygame.font.Font:
    size = max(1, round(settings.FONT_SIZES[font_key] * scale))
    cache_key = (font_key, size)
    if cache_key not in _window_fonts:
        _window_fonts[cache_key] = pygame.font.Font(None, size)
    return _window_fonts[cache_key]
