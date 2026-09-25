"""
cover_state.py

Pantalla de inicio con la imagen de portada (Cover.png).
"""
from __future__ import annotations

import math

import pygame
from gale.state import BaseState

from src.audio import check_sound
from src.rendering.drawing import cover_image, space_background
from src.rendering.theme import COLOR_TEXT_PRIMARY, WINDOW_HEIGHT, WINDOW_WIDTH

class CoverState(BaseState):
    """
    Pantalla de inicio: muestra Cover.png sobre el fondo espacial, con un
    mensaje parpadeante, hasta que el jugador presiona ENTER (ESC sigue
    saliendo del juego: Game2048.on_input la intercepta antes de que
    llegue aquí). Es el primer estado que ve el jugador al arrancar.
    """

    PROMPT_BAR_HEIGHT = 74

    def enter(self, *args, **kwargs) -> None:
        self.prompt_font = pygame.font.SysFont("arial", 24, bold=True)
        self.time = 0.0
        self.image, self.image_rect = cover_image(WINDOW_WIDTH, WINDOW_HEIGHT)

    def exit(self) -> None:
        pass

    def on_input(self, input_id: str, input_data) -> None:
        # Sólo ENTER (main.py la registra como "confirm", tanto la tecla
        # principal como la del teclado numérico) arranca la partida; se
        # ignora cualquier otra tecla, incluidas las flechas.
        if input_id == "confirm" and getattr(input_data, "pressed", False):
            sound = check_sound()
            if sound is not None:
                sound.play()
            self.state_machine.change("play")

    def update(self, dt: float) -> None:
        self.time += dt

    def render(self, surface: pygame.Surface) -> None:
        surface.blit(space_background(*surface.get_size()), (0, 0))
        surface.blit(self.image, self.image_rect)

        # Barra semitransparente en la base, para que el texto se lea sin
        # importar qué haya justo debajo en la imagen de portada.
        bar = pygame.Surface((WINDOW_WIDTH, self.PROMPT_BAR_HEIGHT), pygame.SRCALPHA)
        bar.fill((0, 0, 0, 150))
        surface.blit(bar, (0, WINDOW_HEIGHT - self.PROMPT_BAR_HEIGHT))

        # Parpadeo suave (oscilación seno) en vez de fijo, para que llame
        # la atención como una invitación a jugar.
        alpha = int(160 + 95 * math.sin(self.time * 3.0))
        text = self.prompt_font.render(
            "PRESIONA ENTER PARA JUGAR", True, COLOR_TEXT_PRIMARY
        )
        text.set_alpha(max(0, min(255, alpha)))
        text_rect = text.get_rect(
            center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT - self.PROMPT_BAR_HEIGHT // 2)
        )
        surface.blit(text, text_rect)
