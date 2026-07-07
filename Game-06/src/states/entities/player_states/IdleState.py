
from gale.input_handler import InputData

from src.states.entities.BaseEntityState import BaseEntityState


class IdleState(BaseEntityState):
    def enter(self) -> None:
        self.entity.vx = 0
        self.entity.vy = 0
        
        if self.entity.wounded == True:
            self.entity.texture_id = "Knight_Walk2"
            self.entity.change_animation("walk")
        else:     
            self.entity.texture_id = "Knight_Walk"
            self.entity.change_animation("idle")

    def update(self, dt: float) -> None:
        if self.entity.handle_tilemap_collision_on_bottom(): # or self.entity.items_collision_on_bottom():
            self.entity.vy = 0

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if input_id == "move_left" and input_data.pressed:
            self.entity.flipped = True
            self.entity.change_state("walk", "left")
        elif input_id == "move_right" and input_data.pressed:
            self.entity.flipped = True
            self.entity.change_state("walk", "right")
        elif input_id == "jump" and input_data.pressed:
            self.entity.change_state("jump")
        elif input_id == "attack" and input_data.pressed:
            self.entity.change_state("attack")        
