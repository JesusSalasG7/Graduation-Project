
import pygame

from gale.animation import Animation
from typing import Any
import pygame

from gale.input_handler import InputData
from gale.state import BaseState
from gale.text import Text, render_text
from gale.timer import Timer
from PIL import Image
from src.states import game_states

import settings

class StartState(BaseState):
    def enter(self) -> None:
        self.render_text = True
        self.alpha_transition = 0
        
        # A surface that supports alpha for the screen
        self.screen_alpha_surface = pygame.Surface(
            (settings.VIRTUAL_WIDTH, settings.VIRTUAL_HEIGHT), pygame.SRCALPHA
        )

        # A surface that supports alpha for the title and the menu
        self.text_alpha_surface = pygame.Surface((300, 58), pygame.SRCALPHA)
        pygame.draw.rect(
            self.text_alpha_surface, (255, 255, 255, 128), pygame.Rect(0, 0, 300, 58)
        )
        self.active = True

    def render(self, surface: pygame.Surface) -> None:
        self.surface = surface
        ancho_original, alto_original = settings.TEXTURES["background"].get_size()

        # Calcular factor de escalado
        factor_ancho = settings.VIRTUAL_WIDTH / ancho_original
        factor_alto = settings.VIRTUAL_HEIGHT / alto_original
        factor_escalado = min(factor_ancho, factor_alto)
        
        # Calcular el nuevo tamaño escalado
        nuevo_ancho = int(ancho_original * factor_escalado)
        nuevo_alto = int(alto_original * factor_escalado)
        
        # Escalar la imagen usando smoothscale
        imagen_escalada = pygame.transform.smoothscale(settings.TEXTURES["background"], (nuevo_ancho, nuevo_alto))
        
        # Calcular las coordenadas para centrar la imagen
        x = (settings.VIRTUAL_WIDTH - nuevo_ancho) // 2
        y = (settings.VIRTUAL_HEIGHT - nuevo_alto) // 2
        
        surface.fill((0, 0, 0))
        surface.blit(imagen_escalada, (x, y))
        
        pygame.draw.rect(
            self.screen_alpha_surface,
            (255, 255, 255, self.alpha_transition),
            pygame.Rect(0, 0, settings.VIRTUAL_WIDTH, settings.VIRTUAL_HEIGHT),
        )
        surface.blit(self.screen_alpha_surface, (0, 0))

        if self.render_text:
            render_text(
                    surface,
                    "Presiona ENTER",
                    settings.FONTS["medium"],
                    settings.VIRTUAL_WIDTH // 2,
                    settings.VIRTUAL_HEIGHT // 2 + 40,
                    (197, 195, 198),
                    center=True,
                    shadowed=True,
            )    

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if input_id == "enter" and input_data.pressed and self.active:
            self.active = False
            self.render_text = False
            Timer.tween(
                    1,
                    [(self, {"alpha_transition": 255})],
                    on_finish=self.start_game,
                )

    def start_game(self) -> None:
        self.state_machine.pop()
        self.state_machine.push(game_states.PlayState(self.state_machine), level=2)