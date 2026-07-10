import random
from typing import TypeVar

from src.GameEntity import GameEntity
from src.states.entities import boss_state


class Boss(GameEntity):
    MAX_LIVES = 7

    # The arena floor only exists to the right of this x; the boss must stay
    # inside it once the fight starts instead of wandering the whole level.
    ARENA_MIN_X = 1024

    def __init__(
        self,
        x: float,
        y: float,
        game_level: TypeVar("GameLevel"),
        texture_id: str,
    ) -> None:
        super().__init__(
            x,
            y,
            20,
            59,
            texture_id,
            game_level,
            states={
                "idle": lambda sm: boss_state.IdleStateBoss(self, sm),
                "walk": lambda sm: boss_state.WalkStateBoss(self, sm),
                "attack": lambda sm: boss_state.AttackStateBoss(self, sm),
            },
            animation_defs={
                "idle": {"frames": [0]},
                "walk": {"frames": [0], "interval": 0.20},
                "attack": {"frames": [4]},
            }
        )
        self.wounded = False
        self.lives = Boss.MAX_LIVES
        self.battle_active = False
        self.action_timer = 0.0
        self.recovery_timer = 0.0
        self.state_machine.change("idle")

    def recovery(self) -> None:
        self.wounded = False

    def take_damage(self) -> None:
        self.lives = max(0, self.lives - 1)

    def is_defeated(self) -> bool:
        return self.lives <= 0

    def start_battle(self) -> None:
        """Called once the player crosses into the arena with the key."""
        self.battle_active = True
        self.change_state("idle")
        # Brief telegraph pause before the boss reacts, so the player has a
        # moment to get their bearings when the fight begins.
        self.recovery_timer = 1.2
        self.action_timer = 0.0

    def update(self, dt: float, player: TypeVar("Player") = None) -> None:
        super().update(dt)
        if player is not None:
            self._update_ai(dt, player)

    def _update_ai(self, dt: float, player: TypeVar("Player")) -> None:
        self._clamp_to_arena()

        if not self.battle_active:
            return

        if self.action_timer > 0:
            self.action_timer -= dt
            if self.action_timer <= 0:
                # Every action ends with the boss standing still and
                # vulnerable, guaranteeing the player a window to punish it.
                aggression = 1 - (self.lives / Boss.MAX_LIVES)
                self.change_state("idle")
                self.recovery_timer = max(0.6, 1.1 - aggression * 0.5)
            return

        if self.recovery_timer > 0:
            self.recovery_timer -= dt
            return

        self._choose_action(player)

    def _choose_action(self, player: TypeVar("Player")) -> None:
        # aggression ramps from 0 (full health) towards ~0.86 (near death),
        # making the boss chase/attack more often and recover faster as it
        # takes damage, without ever removing the punish window above.
        aggression = 1 - (self.lives / Boss.MAX_LIVES)
        distance = abs(player.x - self.x)
        attack_range = 70 + aggression * 60
        flipped = player.x > self.x

        if distance <= attack_range:
            self.change_state("attack", flipped)
            self.action_timer = 1.3 - aggression * 0.4
        else:
            self.change_state("walk", flipped)
            self.action_timer = 0.8 + random.uniform(0.0, 0.6 - aggression * 0.3)

    def _clamp_to_arena(self) -> None:
        max_x = self.tilemap.width - self.width
        if self.x < Boss.ARENA_MIN_X:
            self.x = Boss.ARENA_MIN_X
            if self.vx < 0:
                self.vx = -self.vx
        elif self.x > max_x:
            self.x = max_x
            if self.vx > 0:
                self.vx = -self.vx