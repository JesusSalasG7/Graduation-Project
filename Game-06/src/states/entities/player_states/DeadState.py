from src.states.entities.BaseEntityState import BaseEntityState


class DeadState(BaseEntityState):
    def enter(self) -> None:
        self.entity.texture_id = "dead"
        self.entity.change_animation("dead")
        self.entity.vx = 0
        self.entity.vy = 0 
