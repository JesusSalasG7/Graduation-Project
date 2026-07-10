
from src.states.entities.BaseEntityState import BaseEntityState

class IdleStateBoss(BaseEntityState):
    def enter(self) -> None:
        self.entity.vx = 0
        self.entity.vy = 0
        self.entity.flipped = False
        self.entity.change_animation("idle")
        self.entity.texture_id = "dead_Walk"
