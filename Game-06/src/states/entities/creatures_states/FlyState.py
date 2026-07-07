"""
ISPPJ1 2024
Study Case: Super Martian (Platformer)

Author: Alejandro Mujica
alejandro.j.mujic4@gmail.com

This file contains the class SnailWalkState.
"""

from src.GameObject import GameObject
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
        world_width = self.entity.tilemap.width

        if self.entity.x + self.entity.width >= world_width:
            self.entity.x = world_width - self.entity.width
            return True
        elif self.entity.x <= 0:
            self.entity.x = 0
            return True

        if (
            self.entity.handle_tilemap_collision_on_left()
            or self.entity.handle_tilemap_collision_on_right()
        ):
            return True

