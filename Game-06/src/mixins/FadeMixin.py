
from typing import Any, Callable, Optional

import pygame

from gale.timer import Timer


class FadeMixin:
    """
    Shared white fade-to-transition overlay used by full-screen states that
    fade out before switching to another state (e.g. StartState).
    """

    def init_fade(self, width: int, height: int) -> None:
        self.alpha_transition = 0
        self.screen_alpha_surface = pygame.Surface((width, height), pygame.SRCALPHA)

    def render_fade(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(
            self.screen_alpha_surface,
            (255, 255, 255, self.alpha_transition),
            self.screen_alpha_surface.get_rect(),
        )
        surface.blit(self.screen_alpha_surface, (0, 0))

    def start_fade_out(self, duration: float, on_finish: Optional[Callable[[], Any]] = None) -> None:
        Timer.tween(duration, [(self, {"alpha_transition": 255})], on_finish=on_finish)
