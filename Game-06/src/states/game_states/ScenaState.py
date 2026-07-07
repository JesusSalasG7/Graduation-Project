
from typing import Any, Dict
import pygame

import settings

from gale.input_handler import InputData
from gale.state import BaseState
from gale.timer import Timer

from gale.state import StateStack
from gale.text import Text, render_text
from src.states import game_states

class ScenaState(BaseState):
    """Epilogue dialogue shown after the boss is defeated."""

    def enter(self, text: str) -> None:
        self.dialogo = ["Gracias, amigo. Sabía que vendrías.\n Siempre supe que tenías la fuerza para llegar hasta aquí.\nLo que no sabes es que fui yo quien liberó a la criatura.\n Él es el guardián de un poder antiguo, y yo necesitaba su fuerza. \nEl reino no está en peligro...\n El reino necesita este caos para renacer.\nTú, valiente caballero, \neres la pieza que faltaba para completar el ciclo. \nAhora que la has derrotado \nsolo yo puedo usar su poder para moldear el futuro del reino.\n Y tú... serás parte de ese futuro.\nSí, todas mienten. El rey, tú, incluso la criatura... \ntodos han jugado su parte en esta historia.\n Pero al final, sólo uno puede escribir el destino. \nY ese soy yo.","¿Amigo? Crei que... ¿No estás aquí en contra de tu voluntad?\n¿Qué... qué estás diciendo? ¿Era todo una trampa?\n¡No lo puedo creer! ¡Todo ha sido una mentira!\n ¿Nos han usado a todos?\n ¡El rey, el pueblo y yo"]
        self.charaters = ["Princesa","Caballero"]
        self.charaters_index = 0
        self.linea1 = self.dialogo[0].split("\n")
        self.linea2 = self.dialogo[1].split("\n")
        self.talk = [self.linea1,self.linea2]
        self.index = 0
        self.index1 = 0
        self.parrafos = [len(self.linea1),len(self.linea2)]
        self.lineas = 0
        self.parrafor_total = len(self.parrafos)
        self.alpha_transition = 0
        self.text = text
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
        ancho_original, alto_original = settings.TEXTURES[self.text].get_size()

        # Calcular factor de escalado
        factor_ancho = settings.VIRTUAL_WIDTH / ancho_original
        factor_alto = settings.VIRTUAL_HEIGHT / alto_original
        factor_escalado = min(factor_ancho, factor_alto)
        
        # Calcular el nuevo tamaño escalado
        nuevo_ancho = int(ancho_original * factor_escalado)
        nuevo_alto = int(alto_original * factor_escalado)

        # Escalar la imagen usando smoothscale
        imagen_escalada = pygame.transform.smoothscale(settings.TEXTURES[self.text], (nuevo_ancho, nuevo_alto))
        
        # Calcular las coordenadas para centrar la imagen
        x = (settings.VIRTUAL_WIDTH - nuevo_ancho) // 2
        y = (settings.VIRTUAL_HEIGHT - nuevo_alto) // 2

        surface.fill((0, 0, 0))
        surface.blit(imagen_escalada, (x, y))
        
        if self.active:
            render_text(
                surface,
                self.charaters[self.charaters_index],
                settings.FONTS["small"],
                settings.VIRTUAL_WIDTH // 2 - 50,
                settings.VIRTUAL_HEIGHT // 2 + 40,
                (231, 166, 45),
                center=True,
                shadowed=True,
            )

            render_text(
                    surface,
                    self.talk[self.lineas][self.index],
                    settings.FONTS["small"],
                    settings.VIRTUAL_WIDTH // 2,
                    settings.VIRTUAL_HEIGHT // 2 + 50,
                    (197, 195, 198),
                    center=True,
                    shadowed=True,
                )
            
            render_text(
                    surface,
                    "PRESIONA ENTER",
                    settings.FONTS["small"],
                    settings.VIRTUAL_WIDTH // 2,
                    settings.VIRTUAL_HEIGHT // 2 + 70,
                    (197, 195, 198),
                    center=True,
                    shadowed=True,
                )

        pygame.draw.rect(
            self.screen_alpha_surface,
            (255, 255, 255, self.alpha_transition),
            pygame.Rect(0, 0, settings.VIRTUAL_WIDTH, settings.VIRTUAL_HEIGHT),
        )
        surface.blit(self.screen_alpha_surface, (0, 0))

    def on_input(self, input_id: str, input_data: InputData) -> None:

        def finish_dialogs():
             self.state_machine.pop()  # pop this epilogue scene
             self.state_machine.pop()  # pop the dormant GameOverState beneath it
             self.state_machine.push(game_states.FinalState(self.state_machine), level=2)

        if input_id == "enter" and input_data.pressed and self.active:
                if self.index < self.parrafos[self.index1] - 1:
                    self.index += 1
                elif self.parrafor_total - 1:
                    self.index = 0
                    self.index1 += 1
                    self.parrafor_total -= 1
                    self.lineas += 1
                    self.charaters_index += 1
                else:
                    self.index = 0
                    self.lineas = 0
                    self.index1 += 1
                    self.charaters_index = 0
                    self.active = False

                    Timer.tween(
                        1,
                        [(self, {"alpha_transition": 255})],
                        on_finish=finish_dialogs
                    )

