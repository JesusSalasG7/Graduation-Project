"""
Modulo B - Sistema RPG.

This file contains the class Power and the POWERS table: the three
essence-fueled abilities the player can activate without spending
their turn, as long as they can afford the essence cost. The actual
effect (damage/heal/stun) is applied by
src.combat.combat_controller.CombatController.activate_power -- this
module only describes the powers, it doesn't apply them, so the UI
(src.ui.hud) can render their name/cost/color without depending on
combat logic.
"""

from dataclasses import dataclass

import settings


@dataclass(frozen=True)
class Power:
    id: str
    name: str
    essence_kind: str
    cost: int
    key_label: str
    color: tuple
    description: str


POWERS = {
    "fire": Power(
        id="fire",
        name="Fuego Carmesi",
        essence_kind="red",
        cost=12,
        key_label="1",
        color=settings.TILE_COLORS[1],
        description=f"{settings.FIRE_POWER_DAMAGE} de dano directo al enemigo",
    ),
    "shield": Power(
        id="shield",
        name="Egida de Zafiro",
        essence_kind="blue",
        cost=10,
        key_label="2",
        color=settings.TILE_COLORS[2],
        description=f"Cura {settings.SHIELD_POWER_HEAL} HP al jugador",
    ),
    "stasis": Power(
        id="stasis",
        name="Estasis de Eter",
        essence_kind="purple",
        cost=14,
        key_label="3",
        color=settings.TILE_COLORS[3],
        description="El enemigo pierde su proximo turno",
    ),
}
