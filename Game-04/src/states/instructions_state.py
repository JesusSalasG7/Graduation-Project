"""
InstructionsState: static screen shown before StoryState, explaining the
MECHANICS of the game (what appears each round, the time limit, which
button answers what, how many rounds) -- on purpose, NOT the actual rule
that decides a correct answer (see src/signal_check.py). That rule is
meant to be inferred by playing (see README.md "De qué se trata" and
Etapa 1 of the guided session, which has the participant play this game
"broken" before reading the real problem statement), so explaining it
here up front would defeat that.

Unlike StoryState's typewriter effect (which can be skipped mid-way by a
second key press/click before the player has actually read it), this
screen renders instantly and in full, so it can't rush past on a stray
double click.
"""
from typing import Any, List

import pygame

from gale.input_handler import InputData
from gale.state import BaseState

import settings
from src.states.play_state import BUTTON_LABEL_ALTERED, BUTTON_LABEL_STABLE

TITLE = "CÓMO JUGAR"

INSTRUCTION_LINES: List[str] = [
    "Cada ronda te llega una transmisión: una palabra en pantalla.",
    "Tienes 4 segundos para responder antes de que el tiempo se agote.",
    "Elige uno de los dos botones según tu criterio.",
    "Si el tiempo llega a cero sin responder, es Game Over.",
    "Son 8 rondas en total, cada una con una transmisión distinta.",
]

CONTINUE_HINT = "Presiona una tecla o haz clic para continuar"

_LINE_HEIGHT = 16
_BUTTON_LABEL_GAP = 10


class InstructionsState(BaseState):
    def enter(self, *args: Any, **kwargs: Any) -> None:
        pass

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if input_id in ("mouse_click", "confirm") and input_data.pressed:
            self.state_machine.change("story")

    def update(self, dt: float) -> None:
        pass

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(settings.COLORS["background"])

        title_surface = settings.FONTS["title"].render(TITLE, True, settings.COLORS["accent"])
        surface.blit(title_surface, title_surface.get_rect(centerx=settings.VIRTUAL_WIDTH / 2, top=14))

        y = 42
        for line in INSTRUCTION_LINES:
            line_surface = settings.FONTS["hint"].render(line, True, settings.COLORS["text"])
            surface.blit(line_surface, line_surface.get_rect(centerx=settings.VIRTUAL_WIDTH / 2, top=y))
            y += _LINE_HEIGHT

        # Mismos rótulos que va a ver en PlayState (ver PlayState._draw_button
        # / BUTTON_LABEL_*), simplemente listados en vez de como botones
        # clickeables -- para que el jugador los reconozca cuando aparezcan.
        y += _BUTTON_LABEL_GAP
        buttons_line = f"[ {BUTTON_LABEL_STABLE} ]      [ {BUTTON_LABEL_ALTERED} ]"
        buttons_surface = settings.FONTS["prompt"].render(buttons_line, True, settings.COLORS["border"])
        surface.blit(buttons_surface, buttons_surface.get_rect(centerx=settings.VIRTUAL_WIDTH / 2, top=y))

        hint_surface = settings.FONTS["hint"].render(CONTINUE_HINT, True, settings.COLORS["text_dim"])
        surface.blit(
            hint_surface,
            hint_surface.get_rect(centerx=settings.VIRTUAL_WIDTH / 2, bottom=settings.VIRTUAL_HEIGHT - 12),
        )
