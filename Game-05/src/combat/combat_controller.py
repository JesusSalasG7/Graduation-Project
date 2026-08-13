"""
Modulo C - Arbitro de combate (Game Controller).

This file contains the class CombatController: the referee that turns
Modulo A's board outcomes (which TileKind was cleared, how many times,
whether a catalysis happened) into Modulo B stat changes (damage,
essence, healing), decides whose turn it is, resolves the enemy's
attack (or its Estasis de Eter stun), and watches for victory/defeat.

Neither Board nor Combatant/EssencePool depend on this file -- it is
the only place that knows the *rules* connecting board play to combat,
which is what keeps the three modules independently testable.
"""

from typing import Dict, List

import settings
from src.board.tile import TileKind
from src.rpg.essence import EssencePool
from src.rpg.powers import POWERS
from src.rpg.stats import Combatant

_KIND_TO_ESSENCE = {
    TileKind.RED: "red",
    TileKind.BLUE: "blue",
    TileKind.PURPLE: "purple",
}

LOG_HISTORY = 4


class CombatController:
    def __init__(self, player: Combatant, enemy: Combatant, essence: EssencePool) -> None:
        self.player = player
        self.enemy = enemy
        self.essence = essence

        self.enemy_stunned = False
        self.victory = False
        self.defeat = False
        self.log: List[str] = []

    @property
    def game_over(self) -> bool:
        return self.victory or self.defeat

    def log_message(self, message: str) -> None:
        self.log.append(message)
        self.log = self.log[-LOG_HISTORY:]

    def _check_outcome(self) -> None:
        if not self.enemy.is_alive:
            self.victory = True
        elif not self.player.is_alive:
            self.defeat = True

    # -- Board matches -> combat effects ------------------------------

    def apply_kind_effects(self, kind_counts: Dict[TileKind, int]) -> None:
        if self.game_over:
            return

        steel_hits = kind_counts.get(TileKind.STEEL, 0)
        if steel_hits:
            damage = steel_hits * settings.DAMAGE_PER_STEEL_TILE
            dealt = self.enemy.take_damage(damage)
            self.log_message(f"Runas de Acero: {dealt} de dano a {self.enemy.name}")

        for kind, essence_kind in _KIND_TO_ESSENCE.items():
            count = kind_counts.get(kind, 0)
            if count:
                gained = count * settings.ESSENCE_PER_GEM_TILE
                self.essence.add(essence_kind, gained)
                label = settings.ESSENCE_KIND_NAMES[essence_kind]
                self.log_message(f"+{gained} Esencia {label}")

        self._check_outcome()

    # -- Powers -------------------------------------------------------

    def activate_power(self, power_id: str) -> bool:
        if self.game_over:
            return False

        power = POWERS[power_id]
        if not self.essence.has_enough(power.essence_kind, power.cost):
            self.log_message(f"Esencia insuficiente para {power.name}")
            return False

        self.essence.spend(power.essence_kind, power.cost)

        if power_id == "fire":
            dealt = self.enemy.take_damage(settings.FIRE_POWER_DAMAGE)
            self.log_message(f"{power.name}: {dealt} de dano a {self.enemy.name}")
        elif power_id == "shield":
            healed = self.player.heal(settings.SHIELD_POWER_HEAL)
            self.log_message(f"{power.name}: curaste {healed} HP")
        elif power_id == "stasis":
            self.enemy_stunned = True
            self.log_message(f"{power.name}: {self.enemy.name} quedara aturdido")

        self._check_outcome()
        return True

    # -- Enemy turn -----------------------------------------------------

    def run_enemy_turn(self) -> None:
        if self.game_over:
            return

        if self.enemy_stunned:
            self.enemy_stunned = False
            self.log_message(f"{self.enemy.name} esta aturdido y pierde su turno")
            return

        damage = self.enemy.roll_attack()
        dealt = self.player.take_damage(damage)
        self.log_message(f"{self.enemy.name} ataca por {dealt} de dano")
        self._check_outcome()
