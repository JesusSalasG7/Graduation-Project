"""
Rendering-side "falling note": a circle with the letter centered inside
it and a glowing lane-colored outline, owning a plain (x, y) position.

y is derived directly from World's own clock every frame (see sync),
NOT accumulated from a per-frame dt of its own. That distinction matters
now that World.elapsed can itself be snapped straight to the backing
song's real playback position (see World.update / PlayState._current_song_time):
a note whose fall was driven by its own independently-accumulated dt
would drift out of step with that -- tiny per-frame timing differences
between "dt this note added up" and "how far the song's clock actually
moved" compound over a run into a visible mismatch, notes crossing the
hit line on a different rhythm than the beat audibly landing. Deriving y
straight from elapsed every frame instead means there is only ever one
clock in play, so the note can never say anything but exactly where
World says it is.

Deliberately NOT how the actual hit judgement is decided: that still
comes from FallingLetter.hit_time vs. World.elapsed (see World.handle_key),
the model's own clock -- this class only mirrors it for drawing.

Owned and driven by PlayState (see PlayState._sync_notes), not by
TypingRenderer -- keeps note lifecycle (create on spawn, drop after its
resolved flash ends) next to the World events that trigger it, and
TypingRenderer stays a dumb "draw whatever list of notes I'm handed"
view, matching the split Game-01's WorldRenderer keeps.
"""
import pygame

import settings
from src.rendering.pixel_text import render_text

_GLOW_RINGS = ((3, 30), (2, 55), (1, 90))  # (extra radius, alpha), outer to inner


def _dim(color: pygame.Color, visibility: float) -> pygame.Color:
    """`color` lerped towards settings.BACKGROUND_COLOR as `visibility` (0..1) drops."""
    target = settings.BACKGROUND_COLOR
    amount = 1.0 - visibility
    return pygame.Color(
        round(color.r + (target.r - color.r) * amount),
        round(color.g + (target.g - color.g) * amount),
        round(color.b + (target.b - color.b) * amount),
    )


class Note:
    def __init__(self, char: str, x: float, color: pygame.Color, spawn_time: float, hit_time: float) -> None:
        self.char = char
        self.x = x
        self.y = settings.FALL_START_Y
        self.color = color
        self.resolved = False
        self.judgement = None
        self._spawn_time = spawn_time
        self._hit_time = hit_time
        self._resolved_at = None

    def sync(self, elapsed: float) -> None:
        """
        Recomputes y straight from World's own elapsed clock -- see the
        module docstring. No-op once resolved: resolve() already froze y
        at the hit zone, and there's nothing further for elapsed to
        drive on a note that's just playing out its judgement flash.
        """
        if self.resolved:
            return

        span = max(self._hit_time - self._spawn_time, 1e-6)
        progress = min(max((elapsed - self._spawn_time) / span, 0.0), 1.0)
        self.y = settings.FALL_START_Y + progress * (settings.HIT_ZONE_Y - settings.FALL_START_Y)

    def resolve(self, judgement: str, elapsed: float) -> None:
        """Freezes the note at the hit zone, recolored for its judgement flash."""
        self.resolved = True
        self.judgement = judgement
        self.y = settings.HIT_ZONE_Y
        self._resolved_at = elapsed

    def expired(self, elapsed: float) -> bool:
        """Whether PlayState should drop this note from its tracked set."""
        if self.resolved:
            return elapsed - self._resolved_at > settings.LETTER_RESOLVED_FLASH_SECONDS

        # Safety net only -- World always resolves a pending letter itself
        # once its scoring window closes (see World._expire_missed_letter),
        # well before elapsed could ever drift this far past hit_time.
        return elapsed - self._hit_time > settings.OK_WINDOW_SECONDS + 1.0

    def render(self, surface: pygame.Surface, visibility: float = 1.0) -> None:
        """
        `visibility` mirrors World.highway_visibility -- 1.0 normally,
        fading towards 0.0 during a long song pause so a note never sits
        fully bright over an otherwise blacked-out highway (see
        TypingRenderer.render, the one caller that passes anything other
        than the default).
        """
        color = settings.JUDGEMENT_COLORS[self.judgement] if self.resolved else self.color
        if visibility < 1.0:
            color = _dim(color, visibility)
        center = (round(self.x), round(self.y))
        radius = settings.NOTE_RADIUS

        glow = pygame.Surface((radius * 4, radius * 4), pygame.SRCALPHA)
        glow_center = (radius * 2, radius * 2)
        for extra_radius, alpha in _GLOW_RINGS:
            pygame.draw.circle(glow, (*color[:3], alpha), glow_center, radius + extra_radius * 3)
        surface.blit(glow, (center[0] - radius * 2, center[1] - radius * 2))

        pygame.draw.circle(surface, settings.BACKGROUND_COLOR, center, radius)
        pygame.draw.circle(surface, color, center, radius, width=2)

        render_text(surface, self.char, settings.FONTS["note"], center[0], center[1], color, center=True)
