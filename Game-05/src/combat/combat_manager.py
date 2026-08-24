"""
Modulo C - Combate RPG.

CombatManager conecta los matches del tablero (Modulo A) con los
Character de combate: traduce (elemento, cantidad de fichas) en un
EffectResult via src.combat.elements, lo anima y lo aplica sobre
HP/estado, y maneja el turno automatico del enemigo. Tambien dispara
el efecto visual de cada elemento (ver _EFFECT_FACTORIES y
src.combat.effects) del atacante al objetivo -- o sobre el propio
atacante, para Agua, que cura en vez de danar. No conoce Board ni
PlayState mas alla de lo que le pasan como argumentos.
"""

import random

from typing import Callable, List, Optional

from gale.timer import Timer

from src.board.tile import TileKind
from src.combat.character import Character
from src.combat.effects import (
    ArcaneOrb,
    Fireball,
    IceShard,
    LightningBolt,
    RockSpikes,
    VoidPortal,
    WaterSplash,
    WindSlash,
)
from src.combat.elements import compute_effect

# Escalado de dificultad: el enemigo no juega el tablero, asi que no
# puede "mejorar" armando combos el mismo. En cambio, cada
# ENEMY_RAMP_TURNS turnos suyos su ataque simula un match una ficha mas
# grande -- el mismo tramo de multiplicador (3/4/5+) que
# elements.DAMAGE_MULTIPLIER ya le aplica a los matches del jugador --
# hasta el tope ENEMY_MAX_MATCH (5, el mismo limite de
# DAMAGE_MULTIPLIER_MAX). Asi el combate se pone mas duro cuanto mas se
# alarga en vez de quedarse plano para siempre, y premia resolverlo
# rapido con Catalisis grandes.
ENEMY_RAMP_TURNS = 3
ENEMY_MAX_MATCH = 5

# Cada entrada recibe (atacante, objetivo) y arma el efecto visual con
# los anchors que le correspondan -- la mayoria vuela atacante->objetivo,
# pero Agua viaja al reves (cura al atacante) y Electricidad/Tierra/
# Oscuridad son puntos fijos sobre el objetivo (ver cada clase en
# src.combat.effects para el porque).
_EFFECT_FACTORIES = {
    TileKind.FUEGO: lambda a, d: Fireball(a.anchor, d.anchor),
    TileKind.AGUA: lambda a, d: WaterSplash(d.anchor, a.anchor),
    TileKind.TIERRA: lambda a, d: RockSpikes(d.anchor),
    TileKind.AIRE: lambda a, d: WindSlash(a.anchor, d.anchor),
    TileKind.ELECTRICIDAD: lambda a, d: LightningBolt(d.anchor),
    TileKind.HIELO: lambda a, d: IceShard(a.anchor, d.anchor),
    TileKind.MAGIA: lambda a, d: ArcaneOrb(a.anchor, d.anchor),
    TileKind.OSCURIDAD: lambda a, d: VoidPortal(d.anchor),
}


class CombatManager:
    def __init__(self, player: Character, enemy: Character) -> None:
        self.player = player
        self.enemy = enemy
        self._effects: List[object] = []
        self.enemy_turn_count = 0

    def render(self, surface) -> None:
        self.player.render(surface)
        self.enemy.render(surface)
        self._effects = [effect for effect in self._effects if not effect.done]
        for effect in self._effects:
            effect.render(surface)

    def check_result(self) -> Optional[str]:
        if self.enemy.hp <= 0:
            return "victoria"
        if self.player.hp <= 0:
            return "derrota"
        return None

    # -- Turno del jugador ------------------------------------------------

    def apply_player_match(self, kind: TileKind, count: int) -> None:
        self._apply_match(self.player, self.enemy, kind, count)

    # -- Turno del enemigo --------------------------------------------------

    def enemy_turn(self, on_finish: Callable[[], None]) -> None:
        self.enemy_turn_count += 1

        if self.enemy.stunned:
            # Aturdido: pierde el turno, no ataca.
            self.enemy.stunned = False
            on_finish()
            return

        # El enemigo no juega el tablero -- elige un elemento al azar
        # de la misma tabla y lo resuelve con un tamano de match que
        # crece con la duracion del combate (ver _enemy_match_size).
        kind = random.choice(list(TileKind))
        count = self._enemy_match_size()
        self._apply_match(self.enemy, self.player, kind, count=count, on_finish=on_finish)

    def _enemy_match_size(self) -> int:
        """
        Cuantas fichas simula el proximo ataque del enemigo, a efectos
        del multiplicador de elements.compute_effect. Empieza en 3
        (turnos 1..ENEMY_RAMP_TURNS) y sube una ficha cada
        ENEMY_RAMP_TURNS turnos, hasta ENEMY_MAX_MATCH.
        """
        extra = (self.enemy_turn_count - 1) // ENEMY_RAMP_TURNS
        return min(3 + extra, ENEMY_MAX_MATCH)

    # -- Comun --------------------------------------------------------------

    def _apply_match(
        self,
        attacker: Character,
        defender: Character,
        kind: TileKind,
        count: int,
        on_finish: Optional[Callable[[], None]] = None,
    ) -> None:
        if attacker.stunned:
            # Aturdido: el match ya limpio fichas y dio puntaje en el
            # tablero, pero no dispara dano/efecto de combate.
            attacker.stunned = False
            if on_finish:
                on_finish()
            return

        self._effects.append(_EFFECT_FACTORIES[kind](attacker, defender))

        effect = compute_effect(kind, count)
        mult = attacker.next_attack_multiplier
        attacker.next_attack_multiplier = 1.0

        def _impact():
            if effect.heal:
                attacker.heal(round(effect.heal * mult))
            if effect.damage:
                defender.take_damage(round(effect.damage * mult))
            if effect.stun_opponent:
                defender.stunned = True
            if effect.weaken_opponent_next_attack:
                defender.next_attack_multiplier = min(defender.next_attack_multiplier, 0.5)

        attacker.play_attack(on_finish=_impact)

        if on_finish:
            # Le da tiempo a la animacion de ataque + al parpadeo de
            # dano del objetivo antes de devolver el control.
            Timer.after(0.45, on_finish)
