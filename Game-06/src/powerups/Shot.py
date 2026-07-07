"""
ISPPJ1 2024
Study Case: Breakout

Author: Alejandro Mujica
alejandro.j.mujic4@gmail.com

This file contains the class shot.
"""

from typing import Any
from src.GameObject import GameObject

import pygame

import settings
#, width: int, height: int ,id_texture: str 
class Shot(GameObject):
    def __init__(self, x: float, y: float) -> None:
       
        self.x = x
        self.y = y
        self.width = 16
        self.height = 16

        self.vx = 20
        self.texture = settings.TEXTURES["shot"]
        super().__init__(
            x,
            y,
            self.width,
            self.height,
            "shot",
            0,
            {"solidness": dict(top=True, right=True, bottom=True, left=True)}
        )
        
        self.active = True

    def get_collision_rect(self) -> pygame.Rect:
        return pygame.Rect(self.x, self.y, self.width, self.height)


    def collides(self, another: Any) -> bool:
        return self.get_collision_rect().colliderect(another.get_collision_rect())

    def update(self, dt: float) -> None:
            self.x += self.vx * dt
'''
    def render(self, surface):
        image = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        image.fill((0, 0, 0, 0))
        image.blit(self.texture, (0, 0),)

        surface.blit(image, (self.x, self.y))'''





  
