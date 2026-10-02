"""
Crisp text on top of gale's virtual-resolution scaling (same approach
as Game-05/Game-07's src/text.py).

gale renders every frame on the tiny VIRTUAL_WIDTH x VIRTUAL_HEIGHT
(480x270) canvas and then upscales it ~3-4x to the window, which turned
small text (instructions, face-guide letters) into a blurry smear.
render_text() below doesn't blit onto the canvas: it queues the text
(virtual coordinates), and CubeGame draws the queue straight onto the
window after the canvas has been upscaled, with the same font rebuilt
at window resolution (see settings.FONT_SPECS).

The blocky pixel-art titles/buttons/timer go through here too, as a
PixelLabel: rendered tiny without antialiasing and enlarged straight
onto the window by a whole number of window pixels per font pixel.
Enlarging them on the canvas instead (x2/x3) and letting the canvas
upscale stretch them again by a fractional factor (e.g. x3.4) made
some font pixels wider than others, so the letters looked distorted.
Nothing in this game covers the screen after text is drawn, so there's
no overlay() here.
"""
import math
from typing import Any, Dict, List, Optional, Tuple

import pygame

from gale.conf import settings

_queue: List[Tuple[str, str, float, float, Any, Optional[Any], str]] = []
_pixel_queue: List[Tuple["PixelLabel", str, float, float]] = []
_window_fonts: Dict[Tuple[str, int], pygame.font.Font] = {}


# A PixelLabel may be rounded up to the next whole factor only if that
# makes it at most this much larger than its virtual size.
PIXEL_MAX_GROWTH = 1.05


class PixelLabel:
    """Blocky pixel-art text: `small` is the label rendered without
    antialiasing at its font's native size, shown `scale` times larger
    (in virtual pixels)."""

    def __init__(self, small: pygame.Surface, scale: float) -> None:
        self._small = small
        self._scale = scale
        self._scaled: Optional[Tuple[int, pygame.Surface]] = None

    def get_width(self) -> float:
        """Width in virtual pixels (for layout)."""
        return self._small.get_width() * self._scale

    def get_height(self) -> float:
        """Height in virtual pixels (for layout)."""
        return self._small.get_height() * self._scale

    def draw(self, x: float, y: float, anchor: str = "center") -> None:
        """Queues the label at virtual (x, y); `anchor` is any
        pygame.Rect attribute ("center", "midtop", ...)."""
        _pixel_queue.append((self, anchor, x, y))

    def _window_surface(self, font_scale: float) -> pygame.Surface:
        # Whole window pixels per font pixel, so every font pixel ends
        # up the same size. The label may come out a bit smaller than
        # its virtual size (it's anchored, so it stays in place), but
        # barely larger, so it never spills out of its button.
        exact = self._scale * font_scale
        factor = round(exact)
        if factor > exact * PIXEL_MAX_GROWTH:
            factor -= 1
        factor = max(1, factor)
        if self._scaled is None or self._scaled[0] != factor:
            size = (self._small.get_width() * factor, self._small.get_height() * factor)
            self._scaled = (factor, pygame.transform.scale(self._small, size))
        return self._scaled[1]


def pixel_label(text: str, color: Any, scale: float) -> PixelLabel:
    """Builds a PixelLabel of `text` with settings.FONTS["pixel"]."""
    return PixelLabel(settings.FONTS["pixel"].render(text, False, color), scale)


def render_text(
    text: str,
    font_key: str,
    x: float,
    y: float,
    color: Any,
    bgcolor: Optional[Any] = None,
    anchor: str = "topleft",
) -> None:
    """Queues `text` with settings.FONTS[`font_key`] at virtual (x, y);
    `anchor` is any pygame.Rect attribute ("topleft", "center",
    "midleft", ...)."""
    _queue.append((text, font_key, x, y, color, bgcolor, anchor))


def text_size(text: str, font_key: str) -> Tuple[int, int]:
    """Size of `text` in virtual pixels (for layout/wrapping).

    Measured with the window-resolution font that actually draws it
    (see flush) and scaled back down: that font's glyphs aren't exactly
    the virtual font's times the scale, so measuring the virtual font
    left boxes drawn behind the text (tooltips, message panel) too
    short for it."""
    scale = _current_scale()
    width, height = _window_font(font_key, scale).size(text)
    return math.ceil(width / scale), math.ceil(height / scale)


def _current_scale() -> float:
    window = pygame.display.get_surface()
    if window is None:
        return 1.0
    return min(
        window.get_width() / settings.VIRTUAL_WIDTH,
        window.get_height() / settings.VIRTUAL_HEIGHT,
    )


def begin_frame() -> None:
    """Drops anything queued outside the game loop (e.g. a test calling
    a state's render() directly)."""
    _queue.clear()
    _pixel_queue.clear()


def flush(window: pygame.Surface, scale_x: float, scale_y: float) -> None:
    """Draws the queued text onto `window`, mapping virtual coordinates
    with the given scale, and empties the queue."""
    font_scale = min(scale_x, scale_y)
    for text, font_key, x, y, color, bgcolor, anchor in _queue:
        font = _window_font(font_key, font_scale)
        surface = font.render(text, True, color, bgcolor)
        rect = surface.get_rect(**{anchor: (round(x * scale_x), round(y * scale_y))})
        window.blit(surface, rect)
    _queue.clear()

    for label, anchor, x, y in _pixel_queue:
        surface = label._window_surface(font_scale)
        rect = surface.get_rect(**{anchor: (round(x * scale_x), round(y * scale_y))})
        window.blit(surface, rect)
    _pixel_queue.clear()


def _window_font(font_key: str, scale: float) -> pygame.font.Font:
    base_size, bold = settings.FONT_SPECS[font_key]
    size = max(1, round(base_size * scale))
    cache_key = (font_key, size)
    if cache_key not in _window_fonts:
        font = pygame.font.Font(None, size)
        font.set_bold(bold)
        _window_fonts[cache_key] = font
    return _window_fonts[cache_key]
