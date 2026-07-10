
import settings
from src.states.entities.BaseEntityState import BaseEntityState

class AttackStateBoss(BaseEntityState):
    def enter(self, flipped: bool) -> None:
        self.entity.texture_id = "dead_Attack"
        self.showing_attack_texture = True

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
        if not self.bounce_off_world_and_walls():
            return False

        if self.showing_attack_texture:
            self.entity.texture_id = "dead_Walk"
            self.entity.change_animation("idle")
        else:
            self.entity.texture_id = "dead_Attack"
            self.entity.change_animation("walk")
        self.showing_attack_texture = not self.showing_attack_texture

        return True

