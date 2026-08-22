"""
Modulo A - Motor del tablero.

This file contains TileKind (the eight combat elements of Transmutacion
Arcana) and the class Tile. Each kind is blitted from the pre-cut
sprite settings.TILE_SPRITES[kind] (sliced out of tiles.png), so the
rest of the codebase only depends on Tile.kind and Tile.render -- no
other file needs to change if the spritesheet or the kind->row mapping
changes. src.combat.elements maps each TileKind to its combat effect.
"""

from enum import IntEnum

import pygame

import settings


class TileKind(IntEnum):
    FUEGO = 0
    AGUA = 1
    TIERRA = 2
    AIRE = 3
    ELECTRICIDAD = 4
    HIELO = 5
    MAGIA = 6
    OSCURIDAD = 7


class Tile:
    def __init__(self, i: int, j: int, kind: TileKind) -> None:
        self.i = i
        self.j = j
        self.x = self.j * settings.TILE_SIZE
        self.y = self.i * settings.TILE_SIZE
        self.kind = kind

    def render(self, surface: pygame.Surface, offset_x: int, offset_y: int) -> None:
        sprite = settings.TILE_SPRITES[self.kind]
        surface.blit(sprite, (self.x + offset_x, self.y + offset_y))
