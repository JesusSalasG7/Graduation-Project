"""
Reached when a round's countdown hits zero: a short particle explosion
animation, then a static GAME OVER screen. PlayState is the only state
that transitions here (see PlayState.update).
"""
import math
import random
from typing import Any, List

import pygame

from gale.input_handler import InputData
from gale.state import BaseState

import settings

EXPLOSION_DURATION = 1.2  # seconds the particle animation plays for
EXPLOSION_PARTICLE_COUNT = 48
_PARTICLE_SPEED_RANGE = (60.0, 220.0)  # virtual px/second
_PARTICLE_RADIUS_RANGE = (3.0, 7.0)
_PARTICLE_COLORS = (
    "explosion_core",
    "warning",
    "error",
)

GAME_OVER_TITLE = "GAME OVER"
GAME_OVER_SUBTITLE = "El sistema se autodestruyó: no resolviste el código a tiempo."
GAME_OVER_RESTART_HINT = "R = reintentar      ESC = salir"


class _Particle:
    def __init__(self, x: float, y: float, angle_radians: float, speed: float, radius: float, color: pygame.Color) -> None:
        self.x = x
        self.y = y
        self.vx = speed * math.cos(angle_radians)
        self.vy = speed * math.sin(angle_radians)
        self.radius = radius
        self.color = color

    def update(self, dt: float) -> None:
        self.x += self.vx * dt
        self.y += self.vy * dt


def _make_particles() -> List[_Particle]:
    center_x = settings.VIRTUAL_WIDTH / 2
    center_y = settings.VIRTUAL_HEIGHT / 2

    particles = []
    for _ in range(EXPLOSION_PARTICLE_COUNT):
        angle_radians = random.uniform(0, 2 * math.pi)
        speed = random.uniform(*_PARTICLE_SPEED_RANGE)
        radius = random.uniform(*_PARTICLE_RADIUS_RANGE)
        color = settings.COLORS[random.choice(_PARTICLE_COLORS)]
        particles.append(_Particle(center_x, center_y, angle_radians, speed, radius, color))
    return particles


class GameOverState(BaseState):
    def enter(self, *args: Any, **kwargs: Any) -> None:
        self.phase = "exploding"  # "exploding" | "over"
        self.explosion_timer = 0.0
        self.particles = _make_particles()
        settings.SOUNDS["explosion"].play()

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if self.phase != "over":
            return

        if input_id == "restart" and input_data.pressed:
            self.state_machine.change("play")

    def update(self, dt: float) -> None:
        if self.phase != "exploding":
            return

        self.explosion_timer += dt
        for particle in self.particles:
            particle.update(dt)

        if self.explosion_timer >= EXPLOSION_DURATION:
            self.phase = "over"

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(settings.COLORS["background"])

        if self.phase == "exploding":
            progress = min(1.0, self.explosion_timer / EXPLOSION_DURATION)
            shrink_factor = 1.0 - progress
            for particle in self.particles:
                radius = particle.radius * shrink_factor
                if radius > 0:
                    pygame.draw.circle(surface, particle.color, (particle.x, particle.y), radius)
            return

        title_surface = settings.FONTS["game_over_title"].render(GAME_OVER_TITLE, True, settings.COLORS["error"])
        surface.blit(
            title_surface,
            title_surface.get_rect(centerx=settings.VIRTUAL_WIDTH / 2, centery=settings.VIRTUAL_HEIGHT / 2 - 20),
        )

        subtitle_surface = settings.FONTS["hint"].render(GAME_OVER_SUBTITLE, True, settings.COLORS["text_dim"])
        surface.blit(
            subtitle_surface,
            subtitle_surface.get_rect(centerx=settings.VIRTUAL_WIDTH / 2, centery=settings.VIRTUAL_HEIGHT / 2 + 16),
        )

        hint_surface = settings.FONTS["hint"].render(GAME_OVER_RESTART_HINT, True, settings.COLORS["text_dim"])
        surface.blit(
            hint_surface,
            hint_surface.get_rect(centerx=settings.VIRTUAL_WIDTH / 2, bottom=settings.VIRTUAL_HEIGHT - 10),
        )
