
import settings
from src.states.entities.BaseEntityState import BaseEntityState

class WalkStateBoss(BaseEntityState):

    def enter(self, flipped: bool) -> None:
        self.entity.change_animation("walk")
        self.entity.flipped = flipped
        self.entity.vx = -settings.BOSS_SPEED
        if self.entity.flipped:
            self.entity.vx *= -1

    def update(self, dt: float) -> None:
        if self.check_boundary():
            self.entity.vx *= -1
            self.entity.flipped = not self.entity.flipped

    def check_boundary(self) -> bool:
        return self.bounce_off_world_and_walls()
