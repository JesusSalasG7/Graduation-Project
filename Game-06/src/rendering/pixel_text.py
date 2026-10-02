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

Crisp text: gale renders every frame on the VIRTUAL_WIDTH x
VIRTUAL_HEIGHT canvas and then upscales it to the window (x2.5), which
blurred every letter. So render_text() doesn't blit onto the canvas: it
queues the text (same arguments, same virtual coordinates), and
TypeBeatGame draws the queue straight onto the window AFTER the canvas
has been upscaled, with the same font rebuilt at window resolution (see
settings.FONT_SPECS). Same approach as Game-05's src/text.py.

Since queued text ends up above everything on the canvas, anything that
covers the screen with a translucent layer AFTER some text was drawn
(TypingRenderer's end-of-run overlay) must also call overlay() with the
same color, so the text drawn before it gets covered the same way the
canvas does.
"""
from typing import Any, Dict, List, Optional, Tuple

import pygame

import settings

_GLOW_OFFSETS = ((-2, 0), (2, 0), (0, -2), (0, 2))
_GLOW_ALPHA = 150  # halo difuminado (ver _glow): necesita más alfa que las copias nítidas de antes

_queue: List[Tuple[str, Any]] = []
_window_fonts: Dict[Tuple[str, int], pygame.font.Font] = {}
_font_keys: Dict[int, str] = {id(font): key for key, font in settings.FONTS.items()}


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
    alpha: int = 255,
) -> None:
    """Same signature as gale.text.render_text, plus `alpha` (0-255) for
    fading text. `font` must be one of settings.FONTS; `surface` is
    unused (the text is drawn onto the window later, see flush)."""
    _queue.append(
        ("text", (_font_keys[id(font)], text, x, y, color, bgcolor, center, shadowed, alpha))
    )


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

    font_scale = min(scale_x, scale_y)

    # Text queued before an overlay() is drawn straight onto the window
    # (whose canvas pixels the overlay already darkened) with its alpha
    # scaled by how much each later overlay lets through: text * (1 - a)
    # + darkened_canvas * a. The exact result would use the overlay color
    # instead of darkened_canvas; the two differ by a * (1 - a) * (canvas
    # - color), negligible here since the only overlay is the background
    # color over a background-colored screen. Compositing the exact way
    # needs two blend fills over a full-window alpha layer, ~30 ms per
    # frame at 1600x900.
    keep = 1.0
    visible: List[Tuple[Tuple, float]] = []
    for kind, payload in reversed(_queue):
        if kind == "overlay":
            keep *= 1.0 - payload[3] / 255
        else:
            visible.append((payload, keep))

    for payload, text_keep in reversed(visible):
        if text_keep > 0.0:
            _draw(window, payload, scale_x, scale_y, font_scale, text_keep)

    _queue.clear()


def _draw(
    target: pygame.Surface, payload: Tuple, scale_x: float, scale_y: float, font_scale: float, keep: float
) -> None:
    font_key, text, x, y, color, bgcolor, center, shadowed, alpha = payload
    alpha = round(alpha * keep)
    font = _window_font(font_key, font_scale)
    fill_surface = font.render(text, True, color, bgcolor)
    rect = fill_surface.get_rect()
    if center:
        rect.center = (round(x * scale_x), round(y * scale_y))
    else:
        rect.topleft = (round(x * scale_x), round(y * scale_y))

    if shadowed:
        glow_surface, offset = _cached_glow(font_key, font, text, color, font_scale)
        glow_surface.set_alpha(_GLOW_ALPHA * alpha // 255)
        target.blit(glow_surface, rect.move(-offset, -offset))

    if alpha < 255:
        fill_surface.set_alpha(alpha)
    target.blit(fill_surface, rect)


_glow_cache: Dict[Tuple, Tuple[pygame.Surface, int]] = {}
_GLOW_CACHE_MAX = 256


def _cached_glow(
    font_key: str, font: pygame.font.Font, text: str, color: Any, scale: float
) -> Tuple[pygame.Surface, int]:
    """_glow() is a couple of smoothscales -- worth reusing across the
    frames where the same highlighted text stays on screen."""
    key = (font_key, font.get_height(), text, tuple(pygame.Color(color)))
    if key not in _glow_cache:
        if len(_glow_cache) >= _GLOW_CACHE_MAX:
            _glow_cache.clear()
        _glow_cache[key] = _glow(font.render(text, True, color), scale)
    return _glow_cache[key]


def _glow(text_surface: pygame.Surface, scale: float) -> Tuple[pygame.Surface, int]:
    """
    Soft neon halo around `text_surface`: the text is padded, shrunk and
    stretched back (a cheap blur), then its copies offset like the
    original _GLOW_OFFSETS are stacked on top. The old, canvas-drawn glow
    looked soft only because the whole canvas got upscaled; drawn sharp
    at window resolution the same offset copies read as ghost duplicates,
    hence the blur. Returns the glow and how far it extends past the
    text on each side.
    """
    pad = max(2, round(max(abs(d) for offset in _GLOW_OFFSETS for d in offset) * scale * 1.5))
    width, height = text_surface.get_size()
    padded = pygame.Surface((width + 2 * pad, height + 2 * pad), pygame.SRCALPHA)
    for dx, dy in _GLOW_OFFSETS:
        padded.blit(text_surface, (pad + round(dx * scale), pad + round(dy * scale)))
    shrink = 4
    small = pygame.transform.smoothscale(
        padded, (max(1, padded.get_width() // shrink), max(1, padded.get_height() // shrink))
    )
    return pygame.transform.smoothscale(small, padded.get_size()), pad


def _window_font(font_key: str, scale: float) -> pygame.font.Font:
    base_size, bold = settings.FONT_SPECS[font_key]
    size = max(1, round(base_size * scale))
    cache_key = (font_key, size)
    if cache_key not in _window_fonts:
        _window_fonts[cache_key] = pygame.font.SysFont(settings.FONT_FAMILY, size, bold=bold)
    return _window_fonts[cache_key]
