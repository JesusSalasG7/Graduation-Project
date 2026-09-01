"""
HUD bar drawn across the top of the virtual screen during PlayState:
current level, remaining budget, elapsed generations, and whether the
simulation is paused or running.
"""
import pygame

from gale.text import render_text

import settings


def render_hud(
    surface: pygame.Surface,
    level_index: int,
    level_count: int,
    level_name: str,
    generation: int,
    budget_remaining: int,
    budget_total: int,
    running: bool,
) -> None:
    bar = pygame.Rect(0, 0, settings.VIRTUAL_WIDTH, settings.HUD_HEIGHT)
    surface.fill(settings.HUD_BACKGROUND_COLOR, bar)
    pygame.draw.line(
        surface, settings.GRID_LINE_COLOR, (0, settings.HUD_HEIGHT), (settings.VIRTUAL_WIDTH, settings.HUD_HEIGHT)
    )

    render_text(
        surface,
        f"Nivel {level_index + 1}/{level_count}: {level_name}",
        settings.FONTS["hud"],
        8,
        11,
        settings.HUD_TEXT_COLOR,
    )

    render_text(
        surface,
        f"Presupuesto: {budget_remaining}/{budget_total}",
        settings.FONTS["hud"],
        settings.VIRTUAL_WIDTH // 2 - 90,
        11,
        settings.HUD_TEXT_COLOR,
    )

    render_text(
        surface,
        f"Gen: {generation}",
        settings.FONTS["hud"],
        settings.VIRTUAL_WIDTH // 2 + 60,
        11,
        settings.HUD_TEXT_COLOR,
    )

    state_text = "SIMULANDO" if running else "PAUSA"
    render_text(
        surface,
        state_text,
        settings.FONTS["hud"],
        settings.VIRTUAL_WIDTH - 90,
        11,
        settings.HUD_ACCENT_COLOR if running else settings.HUD_TEXT_COLOR,
    )
