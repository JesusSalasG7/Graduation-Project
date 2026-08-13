"""
Modulo B - Sistema RPG.

This file contains the class Combatant: the vital stats shared by the
player and the enemy (HP, max HP, and an optional attack range for
enemies). It knows nothing about the board or about essence -- it is
only the numeric life state that src.combat.combat_controller mutates
in response to matches, powers, and enemy turns.
"""

import random

from typing import Tuple


class Combatant:
    def __init__(
        self, name: str, max_hp: int, attack_range: Tuple[int, int] = (0, 0)
    ) -> None:
        self.name = name
        self.max_hp = max_hp
        self.hp = max_hp
        self.attack_range = attack_range

    @property
    def is_alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, amount: int) -> int:
        amount = max(0, amount)
        dealt = min(self.hp, amount)
        self.hp -= dealt
        return dealt

    def heal(self, amount: int) -> int:
        amount = max(0, amount)
        before = self.hp
        self.hp = min(self.max_hp, self.hp + amount)
        return self.hp - before

    def roll_attack(self) -> int:
        low, high = self.attack_range
        return random.randint(low, high)
