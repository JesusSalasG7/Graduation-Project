"""
Modulo A - Motor del tablero.

This file contains TileKind (the four board pieces of Transmutacion
Arcana) and the class Tile.

There is no spritesheet in this project: every tile is drawn as a
tinted, rounded placeholder rectangle plus a simple vector icon so the
four kinds stay readable even in grayscale. Swap _render_steel /
_render_gem below for real pixel-art blits once art is available; the
rest of the codebase only depends on Tile.kind and Tile.render, so no
other file needs to change.
"""

from enum import IntEnum

import pygame

import settings


class TileKind(IntEnum):
    STEEL = 0  # Runas de Acero: physical damage
    RED = 1  # Gemas Rojas: Esencia Roja
    BLUE = 2  # Gemas Azules: Esencia Azul
    PURPLE = 3  # Gemas Moradas: Esencia Morada


class Tile:
    def __init__(self, i: int, j: int, kind: TileKind) -> None:
        self.i = i
        self.j = j
        self.x = self.j * settings.TILE_SIZE
        self.y = self.i * settings.TILE_SIZE
        self.kind = kind

    def render(self, surface: pygame.Surface, offset_x: int, offset_y: int) -> None:
        size = settings.TILE_SIZE
        rect = pygame.Rect(self.x + offset_x + 2, self.y + offset_y + 2, size - 4, size - 4)

        base_color = settings.TILE_COLORS[self.kind]
        pygame.draw.rect(surface, base_color, rect, border_radius=6)
        pygame.draw.rect(surface, (24, 22, 30), rect, width=2, border_radius=6)

        if self.kind == TileKind.STEEL:
            self._render_rune(surface, rect)
        else:
            self._render_gem(surface, rect, base_color)

    def _render_rune(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        # Placeholder for a "Runa de Acero": a diamond outline with a
        # crossbar, standing in for an engraved metal rune.
        cx, cy = rect.center
        half = rect.width // 2 - 4
        points = [(cx, cy - half), (cx + half, cy), (cx, cy + half), (cx - half, cy)]
        pygame.draw.polygon(surface, (232, 233, 236), points, width=2)
        pygame.draw.line(surface, (232, 233, 236), (cx - half + 3, cy), (cx + half - 3, cy), 2)

    def _render_gem(self, surface: pygame.Surface, rect: pygame.Rect, base_color) -> None:
        # Placeholder for an essence gem: a faceted hexagon with a
        # lighter shine dot, standing in for a cut gemstone.
        cx, cy = rect.center
        w = rect.width // 2 - 4
        h = rect.height // 2 - 4
        points = [
            (cx, cy - h),
            (cx + w, cy - h // 2),
            (cx + w, cy + h // 2),
            (cx, cy + h),
            (cx - w, cy + h // 2),
            (cx - w, cy - h // 2),
        ]
        light = tuple(min(255, c + 60) for c in base_color)
        pygame.draw.polygon(surface, light, points, width=0)
        pygame.draw.polygon(surface, (24, 22, 30), points, width=2)
        pygame.draw.circle(surface, (255, 255, 255), (cx - w // 2, cy - h // 2), 2)
