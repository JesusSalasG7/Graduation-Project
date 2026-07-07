
import pygame

import settings
from src.GameObject import GameObject
from src.states.entities.BaseEntityState import BaseEntityState

class AttackStateBoss(BaseEntityState):
    def enter(self, flipped: bool) -> None:
        self.entity.texture_id = "dead_Attack"
        self.band = True

        self.entity.change_animation("walk")
        self.entity.flipped = flipped
        self.entity.vx = -settings.BOSS_SPEED * 2
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
            if self.band:
                self.entity.texture_id = "dead_Walk"
                self.entity.change_animation("idle")
                self.band = False
            else:
                self.entity.texture_id = "dead_Attack"
                self.entity.change_animation("walk")
                self.band = True
            return True
        elif self.entity.x <= 0:
            self.entity.x = 0
            return True

        if (
            self.entity.handle_tilemap_collision_on_left()
            or self.entity.handle_tilemap_collision_on_right()
        ):
            if self.band:
                self.entity.texture_id = "dead_Walk"
                self.entity.change_animation("idle")
                self.band = False
            else:
                self.entity.texture_id = "dead_Attack"
                self.entity.change_animation("walk")
                self.band = True

            return True

