"""
AchievementsManager: listens to gameplay events raised by PlayState and
unlocks achievements, showing a small fading toast on screen the moment
each one is earned.

Unlocks persist for the lifetime of the running process (module-level
ACHIEVEMENTS + an instance kept in ConwayGame), so a title earned on one
level stays unlocked when the player jumps to another.
"""
from typing import Dict, List, Tuple

import pygame

from gale.text import render_text

import settings

Coord = Tuple[int, int]

ACHIEVEMENTS: Dict[str, Tuple[str, str]] = {
    "first_click": ("Primer Clic", "Coloca tu primera celula."),
    "max_efficiency": (
        "Eficiencia Maxima",
        "Gana un nivel usando la mitad o menos del presupuesto.",
    ),
    "chain_reaction": (
        "Reaccion en Cadena",
        "Provoca 8 o mas nacimientos en una sola generacion.",
    ),
}


class _Toast:
    def __init__(self, title: str) -> None:
        self.title = title
        self.time_remaining = settings.ACHIEVEMENT_TOAST_DURATION


class AchievementsManager:
    def __init__(self) -> None:
        self.unlocked: set = set()
        self._toasts: List[_Toast] = []

    def is_unlocked(self, achievement_id: str) -> bool:
        return achievement_id in self.unlocked

    def unlock(self, achievement_id: str) -> None:
        if achievement_id in self.unlocked:
            return

        self.unlocked.add(achievement_id)
        title, _description = ACHIEVEMENTS[achievement_id]
        self._toasts.append(_Toast(title))

    def on_cell_placed(self, player_cells_count: int) -> None:
        if player_cells_count == 1:
            self.unlock("first_click")

    def on_generation(self, births: int) -> None:
        if births >= settings.ACHIEVEMENT_CHAIN_REACTION_BIRTHS:
            self.unlock("chain_reaction")

    def on_victory(self, budget_total: int, budget_remaining: int) -> None:
        used = budget_total - budget_remaining
        if budget_total > 0 and used <= budget_total * settings.ACHIEVEMENT_EFFICIENCY_THRESHOLD:
            self.unlock("max_efficiency")

    def update(self, dt: float) -> None:
        for toast in self._toasts:
            toast.time_remaining -= dt
        self._toasts = [t for t in self._toasts if t.time_remaining > 0]

    def render(self, surface: pygame.Surface) -> None:
        x = 8
        y = settings.HUD_HEIGHT + 6

        for toast in self._toasts:
            text = f"* Logro desbloqueado: {toast.title}"
            render_text(
                surface,
                text,
                settings.FONTS["toast"],
                x,
                y,
                settings.ACHIEVEMENT_TOAST_COLOR,
                bgcolor=pygame.Color(0, 0, 0),
                center=False,
                shadowed=True,
            )
            y += 16
