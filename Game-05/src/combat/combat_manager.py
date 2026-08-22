"""
Modulo C - Combate RPG.

CombatManager conecta los matches del tablero (Modulo A) con los
Character de combate: traduce (elemento, cantidad de fichas) en un
EffectResult via src.combat.elements, lo anima y lo aplica sobre
HP/estado, y maneja el turno automatico del enemigo. No conoce Board
ni PlayState mas alla de lo que le pasan como argumentos.
"""

import random

from typing import Callable, Optional

from gale.timer import Timer

from src.board.tile import TileKind
from src.combat.character import Character
from src.combat.elements import compute_effect


class CombatManager:
    def __init__(self, player: Character, enemy: Character) -> None:
        self.player = player
        self.enemy = enemy

    def render(self, surface) -> None:
        self.player.render(surface)
        self.enemy.render(surface)

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
        if self.enemy.stunned:
            # Aturdido: pierde el turno, no ataca.
            self.enemy.stunned = False
            on_finish()
            return

        # El enemigo no juega el tablero -- elige un elemento al azar
        # de la misma tabla y siempre lo resuelve como un match base
        # (3 fichas, multiplicador x1.0).
        kind = random.choice(list(TileKind))
        self._apply_match(self.enemy, self.player, kind, count=3, on_finish=on_finish)

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
