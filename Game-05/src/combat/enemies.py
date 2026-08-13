"""
Modulo C - Arbitro de combate.

This file contains make_enemy, building a src.rpg.stats.Combatant plus
its portrait color and pixel-art sprite from settings.ENEMY_ROSTER. The
roster is a short, fixed campaign (4 foes) rather than infinite
scaling, so a full playthrough of Transmutacion Arcana has a real
ending.
"""

from typing import Tuple

import pygame

import settings
from src.rpg.stats import Combatant

ENEMY_COUNT = len(settings.ENEMY_ROSTER)


def make_enemy(level: int) -> Tuple[Combatant, tuple, pygame.Surface]:
    """
    :param level: 1-based index into settings.ENEMY_ROSTER. Levels
    beyond the roster's length repeat the last (strongest) enemy, so
    the game degrades gracefully instead of crashing if it is ever
    driven past ENEMY_COUNT.
    :returns: (enemy, portrait_color, portrait_sprite)
    """
    index = min(level, ENEMY_COUNT) - 1
    template = settings.ENEMY_ROSTER[index]
    enemy = Combatant(template["name"], template["max_hp"], template["attack"])
    sprite = settings.TEXTURES[template["sprite_file"]]
    return enemy, template["color"], sprite
