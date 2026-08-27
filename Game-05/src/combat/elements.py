"""
Modulo C - Combate RPG.

Configuracion pura de los 8 elementos: cuanto dano/curacion hace cada
uno y que efecto adicional aplica. No depende de pygame ni sabe nada de
Character/CombatManager -- solo traduce (elemento, cantidad de fichas)
en un EffectResult que CombatManager sabe aplicar.
"""

import random

from dataclasses import dataclass

from src.board.tile import TileKind

# Cuantas fichas tuvo el match -> multiplicador sobre el dano/curacion
# base del elemento (3 = base, 4 = combo, 5+ = combo grande).
DAMAGE_MULTIPLIER = {3: 1.0, 4: 1.5}
DAMAGE_MULTIPLIER_MAX = 2.0  # aplica para 5 o mas fichas


def _multiplier_for(count: int) -> float:
    if count >= 5:
        return DAMAGE_MULTIPLIER_MAX
    return DAMAGE_MULTIPLIER.get(count, 1.0)


@dataclass
class EffectResult:
    """
    Resultado ya resuelto de aplicar un elemento: CombatManager solo
    tiene que sumar/restar estos valores, sin conocer las reglas de
    cada elemento.
    """

    damage: int = 0
    heal: int = 0
    ignore_defense: bool = False
    stun_opponent: bool = False
    weaken_opponent_next_attack: bool = False
    is_crit: bool = False


# Cada entrada define el nombre en pantalla, el color de su destello, y
# una funcion que recibe el multiplicador de combo ya resuelto y
# devuelve el EffectResult. Los porcentajes de probabilidad (aturdir,
# critico) se tiran aca mismo con random.random().
ELEMENTOS = {
    TileKind.FUEGO: {
        "nombre": "Fuego",
        "color": (235, 90, 40),
        "resolver": lambda mult: EffectResult(damage=round(18 * mult)),
    },
    TileKind.AGUA: {
        "nombre": "Agua",
        "color": (70, 140, 235),
        "resolver": lambda mult: EffectResult(heal=round(15 * mult)),
    },
    TileKind.TIERRA: {
        "nombre": "Tierra",
        "color": (150, 105, 60),
        "resolver": lambda mult: EffectResult(
            damage=round(12 * mult), weaken_opponent_next_attack=True
        ),
    },
    TileKind.AIRE: {
        "nombre": "Aire",
        "color": (190, 200, 210),
        "resolver": lambda mult: EffectResult(damage=round(10 * mult)),
    },
    TileKind.ELECTRICIDAD: {
        "nombre": "Electricidad",
        "color": (230, 200, 40),
        "resolver": lambda mult: EffectResult(
            damage=round(12 * mult), stun_opponent=random.random() < 0.3
        ),
    },
    TileKind.HIELO: {
        "nombre": "Hielo",
        "color": (110, 210, 220),
        "resolver": lambda mult: EffectResult(
            damage=round(8 * mult), weaken_opponent_next_attack=True
        ),
    },
    TileKind.MAGIA: {
        "nombre": "Magia",
        "color": (170, 90, 220),
        "resolver": lambda mult: _resolver_magia(mult),
    },
    TileKind.OSCURIDAD: {
        "nombre": "Oscuridad",
        "color": (80, 60, 90),
        "resolver": lambda mult: EffectResult(damage=round(16 * mult), ignore_defense=True),
    },
}


def _resolver_magia(mult: float) -> EffectResult:
    base = random.uniform(8, 24)
    is_crit = random.random() < 0.2
    if is_crit:
        base *= 2
    return EffectResult(damage=round(base * mult), is_crit=is_crit)


def compute_effect(kind: TileKind, count: int) -> EffectResult:
    """
    Calcula el efecto de un match del elemento `kind` con `count`
    fichas eliminadas. El multiplicador de combo (3/4/5+) ya viene
    aplicado en el resultado.
    """
    mult = _multiplier_for(count)
    return ELEMENTOS[kind]["resolver"](mult)
