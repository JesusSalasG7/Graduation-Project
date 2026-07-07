
from gale.input_handler import InputData

import settings
from src.states.entities.BaseEntityState import BaseEntityState
from gale.timer import Timer

class AttackState(BaseEntityState):
    def enter(self) -> None:
        self.entity.vx = 0
        self.entity.vy = 0
        
        if self.entity.wounded == True:
            self.entity.texture_id = "Knight_Attack2"
        else:     
            self.entity.texture_id = "Knight_Attack" 

        self.entity.change_animation("attack") 
        settings.SOUNDS["attack"].stop()
        settings.SOUNDS["attack"].play()
       
    def on_input(self, input_id: str, input_data: InputData) -> None:
        if input_id == "move_left" and input_data.pressed:
            self.entity.change_state("walk", "left")
        elif input_id == "move_right" and input_data.pressed:
            self.entity.change_state("walk", "right")
        elif input_id == "attack" and input_data.released:

                self.entity.change_state("idle")