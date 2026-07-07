
import pygame

from gale.input_handler import InputData
from gale.state import BaseState
from gale.text import render_text

from gale.animation import Animation
from src.states import game_states


import settings

class GameOverState(BaseState):
    def enter(self,level) -> None:
        self.level = level
        settings.SOUNDS["gameover"].play()

        self.animation = {}  
        algo = Animation(
                [0,1,2,3,4,5,6,7],
                0.13,  # Given interval or zero
                0,
            )
        def set_active():
            self.active = True
        algo.on_finish = set_active
        self.animation["dead"] = algo
        self.current_animation = None
        self.frame_index = -1
        self.active = False
        self.change_animation("dead")

    def update(self, dt: float) -> None:

        if self.current_animation:
            self.current_animation.update(dt)
            self.frame_index = self.current_animation.get_current_frame()    

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if input_id == "enter" and input_data.pressed and self.active:
            settings.SOUNDS["gameover"].stop()
            self.state_machine.pop()
            self.state_machine.push(game_states.PlayState(self.state_machine), level = self.level)

    def render(self, surface: pygame.Surface) -> None:

        if self.level == 1:
            surface.fill((100, 100, 100))
        else:
            surface.fill((51, 25, 102))  

        render_text(
            surface,
            "Game Over",
            settings.FONTS["medium"],
            settings.VIRTUAL_WIDTH // 2,
            20,
            (255, 255, 255),
            center=True,
            shadowed=True,
        )


        texture = settings.TEXTURES["dead"]
        frame = settings.FRAMES["dead"][self.frame_index]
        image = pygame.Surface((32, 23), pygame.SRCALPHA)
        image.fill((0, 0, 0, 0))
        image.blit(texture, (0, 0), frame)


        surface.blit(image,(settings.VIRTUAL_WIDTH // 2 - 16 , settings.VIRTUAL_HEIGHT // 2),)

        render_text(
            surface,
            "Press Enter to play again",
            settings.FONTS["small"],
            settings.VIRTUAL_WIDTH // 2,
            settings.VIRTUAL_HEIGHT - 20,
            (255, 255, 255),
            center=True,
            shadowed=True,
        )


    def change_animation(self, animation_id: str) -> None:
        new_animation = self.animation[animation_id]
        if new_animation != self.current_animation:
            self.current_animation = new_animation
            self.current_animation.reset()
            self.frame_index = self.current_animation.get_current_frame()
        
        
