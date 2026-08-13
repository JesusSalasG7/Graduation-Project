"""
Modulo B - Sistema RPG.

This file contains the class EssencePool: the player's reserves of Red,
Blue and Purple essence, gathered from Match-3s of the corresponding
gems and spent to activate powers (src.rpg.powers).
"""

import settings


class EssencePool:
    KINDS = ("red", "blue", "purple")

    def __init__(self) -> None:
        self.red = 0
        self.blue = 0
        self.purple = 0

    def add(self, kind: str, amount: int) -> None:
        current = getattr(self, kind)
        setattr(self, kind, min(settings.MAX_ESSENCE, current + max(0, amount)))

    def has_enough(self, kind: str, amount: int) -> bool:
        return getattr(self, kind) >= amount

    def spend(self, kind: str, amount: int) -> bool:
        if not self.has_enough(kind, amount):
            return False
        setattr(self, kind, getattr(self, kind) - amount)
        return True
