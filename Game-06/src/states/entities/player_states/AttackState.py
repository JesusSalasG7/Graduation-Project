
from gale.input_handler import InputData

import settings
from src.states.entities.BaseEntityState import BaseEntityState

class AttackState(BaseEntityState):
    def enter(self) -> None:
        self.entity.vx = 0

        self.entity.texture_id = self.entity.texture_for("Knight_Attack")
        self.entity.change_animation("attack")
        settings.SOUNDS["attack"].stop()
        settings.SOUNDS["attack"].play()

    def update(self, dt: float) -> None:
        # Attacking can now be triggered mid-air (see JumpState/FallState),
        # so gravity keeps being applied here too; otherwise the player
        # would freeze in place mid-jump and float forever afterwards.
        self.entity.vy = min(self.entity.vy + settings.GRAVITY * dt, settings.MAX_FALL_SPEED)

        if self.entity.handle_tilemap_collision_on_bottom():
            self.entity.vy = 0

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if input_id == "move_left" and input_data.pressed:
            self.entity.change_state("walk", "left")
        elif input_id == "move_right" and input_data.pressed:
            self.entity.change_state("walk", "right")
        elif input_id == "attack" and input_data.released:
            if self.entity.check_floor():
                self.entity.change_state("idle")
            else:
                self.entity.change_state("fall")