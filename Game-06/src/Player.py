
from typing import TypeVar

import pygame

from gale.input_handler import InputData

from src.GameEntity import GameEntity
from src.states.entities import player_states


class Player(GameEntity):
    def __init__(self, x: int, y: int, game_level: TypeVar("GameLevel")) -> None:
        super().__init__(
            x,
            y,
            16,
            17,
            "Knight_Walk",
            game_level,
            states={
                "idle": lambda sm: player_states.IdleState(self, sm),
                "walk": lambda sm: player_states.WalkState(self, sm),
                "jump": lambda sm: player_states.JumpState(self, sm),
                "fall": lambda sm: player_states.FallState(self, sm),
                "dead": lambda sm: player_states.DeadState(self, sm),
                "attack": lambda sm: player_states.AttackState(self, sm),
            },
            animation_defs={
                "idle": {"frames": [0]},
                "walk": {"frames": [0, 2, 4, 6], "interval": 0.15},
                "jump": {"frames": [2]},
                "attack": {"frames": [0, 1], "interval": 0.10},
                "dead": {"frames": [0, 1, 2, 3, 4, 5, 6, 7], "interval": 0.10, "loops": 0},
            },
        )
        self.wounded = False
        self.powerUP = True
        self.pickup_key = False
        self.key_puzzle_pending = False
        self.open_door =False

        def set_dead():
            self.is_dead = True

        self.animations["dead"].on_finish = set_dead

    def recovery(self) -> None:
        self.wounded = False

    def change_texture(self, texture_id: str) -> None:
        self.texture_id = texture_id

    def attack_zone(self,flipped)  -> None:
        if flipped:
            return pygame.Rect(self.x - 9, self.y, self.width, self.height)
        else: 
            return pygame.Rect(self.x, self.y, self.width + 9, self.height)

    def on_input(self, input_id: str, input_data: InputData) -> None:
        self.state_machine.on_input(input_id, input_data)