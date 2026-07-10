"""
ISPPJ1 2024
Study Case: Super Martian (Platformer)

Author: Alejandro Mujica
alejandro.j.mujic4@gmail.com

This file contains the class SnailWalkState.
"""

from src.states.entities.BaseEntityState import BaseEntityState


class FlyState(BaseEntityState):
    def enter(self, flipped: bool) -> None:
        self.entity.change_animation("fly")
        self.entity.flipped = flipped
        self.entity.vx = -self.entity.walk_speed
        if self.entity.flipped:
            self.entity.vx *= -1

    def update(self, dt: float) -> None:
        if self.check_boundary():
            self.entity.vx *= -1
            self.entity.flipped = not self.entity.flipped

    def check_boundary(self) -> bool:
        return self.bounce_off_world_and_walls()

