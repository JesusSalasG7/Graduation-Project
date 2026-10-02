"""
InstructionsState: static screen shown before StoryState, explaining the
MECHANICS of the game (what appears each round, the time limit, which
button answers what, how many rounds) and the rule that decides a
correct answer (palindrome -> stable, anything else -> altered; see
src/signal_check.py), so the player knows what to look for from the
very first round.

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
from src import text
from src.states.play_state import BUTTON_LABEL_ALTERED, BUTTON_LABEL_STABLE

TITLE = "CÓMO JUGAR"

INSTRUCTION_LINES: List[str] = [
    "Cada ronda te llega una transmisión: una palabra en pantalla.",
    "Tienes 4 segundos para responder antes de que el tiempo se agote.",
    "Si la palabra es un palíndromo (se lee igual al revés),",
    f"es {BUTTON_LABEL_STABLE}; si no lo es, es {BUTTON_LABEL_ALTERED}.",
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

        text.draw_text(surface, "title", TITLE, settings.COLORS["accent"], centerx=settings.VIRTUAL_WIDTH / 2, top=14)

        y = 42
        for line in INSTRUCTION_LINES:
            text.draw_text(surface, "hint", line, settings.COLORS["text"], centerx=settings.VIRTUAL_WIDTH / 2, top=y)
            y += _LINE_HEIGHT

        # Mismos rótulos que va a ver en PlayState (ver PlayState._draw_button
        # / BUTTON_LABEL_*), simplemente listados en vez de como botones
        # clickeables -- para que el jugador los reconozca cuando aparezcan.
        y += _BUTTON_LABEL_GAP
        buttons_line = f"[ {BUTTON_LABEL_STABLE} ]      [ {BUTTON_LABEL_ALTERED} ]"
        text.draw_text(
            surface, "prompt", buttons_line, settings.COLORS["border"],
            centerx=settings.VIRTUAL_WIDTH / 2, top=y,
        )

        text.draw_text(
            surface, "hint", CONTINUE_HINT, settings.COLORS["text_dim"],
            centerx=settings.VIRTUAL_WIDTH / 2, bottom=settings.VIRTUAL_HEIGHT - 12,
        )
