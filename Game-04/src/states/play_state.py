"""
The game's single play screen: draws TOTAL_ROUNDS strings out of
WORD_POOL, at random and without repeats, one at a time, and collects
the player's stable/altered call for each within TIME_LIMIT seconds --
letting the countdown reach zero sends the player to GameOverState. The
verification rule itself lives in src/signal_check.py, kept separate
from this rendering/input code so it can be tested in isolation.
"""
import random
import time
from typing import Any, Dict, List, Optional, Tuple

import pygame

from gale.input_handler import InputData, MouseClickData, MouseMotionData
from gale.state import BaseState

import settings
from src.signal_check import is_stable_signal

# A mix of real Spanish words that keep their shape when reversed and
# ones that don't -- which is which is never stored anywhere as data,
# it is always derived by calling is_stable_signal() at answer time.
# Every match draws TOTAL_ROUNDS of these at random (see enter()), so
# consecutive playthroughs rarely show the same set of words.
WORD_POOL: List[str] = [
    "RADAR",
    "RECONOCER",
    "SOMETEMOS",
    "ANILINA",
    "ROTOR",
    "SALAS",
    "SOMOS",
    "SERES",
    "ORO",
    "OSO",
    "OJO",
    "ALA",
    "AMA",
    "ANA",
    "EJE",
    "RAJAR",
    "CODIGO",
    "PYTHON",
    "JUEGO",
    "SISTEMAS",
    "VENTANA",
    "TELEFONO",
    "MENSAJE",
    "CIRCUITO",
    "NUMERO",
    "TECLADO",
    "PANTALLA",
    "MONITOR",
    "REFLEJO",
    "PATRON",
    "LOGICA",
    "ALGORITMO",
]
TOTAL_ROUNDS = 8

ANSWER_STABLE = "stable"
ANSWER_ALTERED = "altered"

SCORE_PER_CORRECT = 100
FEEDBACK_DURATION = 1.2  # seconds the round's outcome stays on screen
ERROR_DISPLAY_DURATION = 2.0  # seconds a "function pending" notice stays up
TIME_LIMIT = 4.0  # seconds to answer a round before it's game over
TIMER_WARNING_THRESHOLD = 2.5  # seconds remaining at which the timer turns amber
TIMER_DANGER_THRESHOLD = 1.5  # seconds remaining at which the timer turns red

PROMPT_QUESTION = "¿La señal conserva su patrón al cruzar el espejo?"
BUTTON_LABEL_STABLE = "SEÑAL ESTABLE"
BUTTON_LABEL_ALTERED = "SEÑAL ALTERADA"
FEEDBACK_SUCCESS_TEXT = "Acceso autorizado."
FEEDBACK_ERROR_TEXT = "La señal no coincide con su reflejo."
ERROR_FUNCTION_MISSING_TEXT = "Falta implementar el verificador de señal."

GameLogEntry = Dict[str, Any]


def _virtual_position(position: Tuple[int, int]) -> Tuple[float, float]:
    x, y = position
    return (
        x * settings.VIRTUAL_WIDTH / settings.WINDOW_WIDTH,
        y * settings.VIRTUAL_HEIGHT / settings.WINDOW_HEIGHT,
    )


def _draw_button(surface: pygame.Surface, rect: pygame.Rect, label: str, is_hovered: bool) -> None:
    background_color = settings.COLORS["button_hover"] if is_hovered else settings.COLORS["button_background"]
    pygame.draw.rect(surface, background_color, rect, border_radius=6)
    pygame.draw.rect(surface, settings.COLORS["button_border"], rect, width=2, border_radius=6)
    label_surface = settings.FONTS["button"].render(label, True, settings.COLORS["text"])
    surface.blit(label_surface, label_surface.get_rect(center=rect.center))


class PlayState(BaseState):
    def enter(self, *args: Any, **kwargs: Any) -> None:
        button_width, button_height = 190, 56
        gap = 24
        total_width = button_width * 2 + gap
        left = (settings.VIRTUAL_WIDTH - total_width) / 2
        top = 175

        self.stable_button_rect = pygame.Rect(left, top, button_width, button_height)
        self.altered_button_rect = pygame.Rect(
            left + button_width + gap, top, button_width, button_height
        )
        self.hover_position: Optional[Tuple[float, float]] = None

        self.current_round = 0
        self.score = 0
        self.correct_count = 0
        self.wrong_count = 0
        self.game_log: List[GameLogEntry] = []
        self.match_start_time = time.perf_counter()

        self.phase = "waiting"  # "waiting" | "feedback"
        self.feedback_message = ""
        self.feedback_color = settings.COLORS["text"]
        self.feedback_timer = 0.0

        self.error_message: Optional[str] = None
        self.error_timer = 0.0

        # A fresh random draw every match: TOTAL_ROUNDS distinct words
        # out of WORD_POOL, in random order, so consecutive playthroughs
        # rarely show the same words in the same order.
        self.round_strings: List[str] = random.sample(WORD_POOL, TOTAL_ROUNDS)

        self._start_round()

    def _start_round(self) -> None:
        if self.current_round >= TOTAL_ROUNDS:
            total_time_ms = round((time.perf_counter() - self.match_start_time) * 1000)
            self.state_machine.change(
                "results",
                game_log=self.game_log,
                correct_count=self.correct_count,
                wrong_count=self.wrong_count,
                score=self.score,
                total_time_ms=total_time_ms,
            )
            return

        self.current_string = self.round_strings[self.current_round]
        self.current_round += 1
        self.round_start_time = time.perf_counter()
        self.phase = "waiting"
        self.feedback_message = ""
        self.time_remaining = TIME_LIMIT
        settings.SOUNDS["clock"].play(loops=-1)

    def _answer(self, player_answer: str) -> None:
        if self.phase != "waiting":
            return

        try:
            self._handle_answer(player_answer)
        except NotImplementedError:
            self.error_message = ERROR_FUNCTION_MISSING_TEXT
            self.error_timer = 0.0

    def _handle_answer(self, player_answer: str) -> None:
        response_time_ms = round((time.perf_counter() - self.round_start_time) * 1000)
        correct_answer = ANSWER_STABLE if is_stable_signal(self.current_string) else ANSWER_ALTERED
        is_correct = player_answer == correct_answer

        if is_correct:
            self.score += SCORE_PER_CORRECT
            self.correct_count += 1
            self.feedback_color = settings.COLORS["success"]
            self.feedback_message = FEEDBACK_SUCCESS_TEXT
            settings.SOUNDS["correct"].play()
        else:
            self.wrong_count += 1
            self.feedback_color = settings.COLORS["error"]
            self.feedback_message = FEEDBACK_ERROR_TEXT
            settings.SOUNDS["incorrect"].play()

        self.game_log.append(
            {
                "round": self.current_round,
                "string": self.current_string,
                "player_answer": player_answer,
                "correct_answer": correct_answer,
                "is_correct": is_correct,
                "response_time_ms": response_time_ms,
            }
        )

        self.phase = "feedback"
        self.feedback_timer = 0.0
        settings.SOUNDS["clock"].stop()

    def exit(self) -> None:
        settings.SOUNDS["clock"].stop()

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if input_id == "mouse_click" and isinstance(input_data, MouseClickData):
            if input_data.pressed:
                position = _virtual_position(input_data.position)
                if self.stable_button_rect.collidepoint(position):
                    self._answer(ANSWER_STABLE)
                elif self.altered_button_rect.collidepoint(position):
                    self._answer(ANSWER_ALTERED)
        elif input_id == "mouse_motion" and isinstance(input_data, MouseMotionData):
            self.hover_position = _virtual_position(input_data.position)

    def update(self, dt: float) -> None:
        if self.phase == "waiting":
            self.time_remaining -= dt
            if self.time_remaining <= 0:
                self.time_remaining = 0.0
                self.state_machine.change("game_over")
                return

        if self.phase == "feedback":
            self.feedback_timer += dt
            if self.feedback_timer >= FEEDBACK_DURATION:
                self._start_round()

        if self.error_message is not None:
            self.error_timer += dt
            if self.error_timer >= ERROR_DISPLAY_DURATION:
                self.error_message = None

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(settings.COLORS["background"])

        title_surface = settings.FONTS["title"].render("ESPEJO DE CÓDIGOS", True, settings.COLORS["accent"])
        surface.blit(title_surface, title_surface.get_rect(centerx=settings.VIRTUAL_WIDTH / 2, top=14))

        round_text = f"RONDA {self.current_round} / {TOTAL_ROUNDS}"
        round_surface = settings.FONTS["hint"].render(round_text, True, settings.COLORS["text_dim"])
        surface.blit(round_surface, round_surface.get_rect(right=settings.VIRTUAL_WIDTH - 16, top=16))

        if self.time_remaining <= TIMER_DANGER_THRESHOLD:
            timer_color = settings.COLORS["error"]
        elif self.time_remaining <= TIMER_WARNING_THRESHOLD:
            timer_color = settings.COLORS["warning"]
        else:
            timer_color = settings.COLORS["text"]
        # Sub-second digits included on purpose: the digits churning every
        # frame reads as "the clock is really running out", more so than a
        # rounded whole-second countdown would.
        timer_text = f"{self.time_remaining:.3f}s"
        timer_surface = settings.FONTS["timer"].render(timer_text, True, timer_color)
        surface.blit(timer_surface, timer_surface.get_rect(centerx=settings.VIRTUAL_WIDTH / 2, top=34))

        transmission_text = f"TRANSMISIÓN RECIBIDA: {self.current_string}"
        transmission_surface = settings.FONTS["transmission"].render(transmission_text, True, settings.COLORS["text"])
        surface.blit(
            transmission_surface,
            transmission_surface.get_rect(centerx=settings.VIRTUAL_WIDTH / 2, top=70),
        )

        prompt_surface = settings.FONTS["prompt"].render(PROMPT_QUESTION, True, settings.COLORS["text_dim"])
        surface.blit(prompt_surface, prompt_surface.get_rect(centerx=settings.VIRTUAL_WIDTH / 2, top=105))

        stable_hovered = self.hover_position is not None and self.stable_button_rect.collidepoint(
            self.hover_position
        )
        altered_hovered = self.hover_position is not None and self.altered_button_rect.collidepoint(
            self.hover_position
        )
        _draw_button(surface, self.stable_button_rect, BUTTON_LABEL_STABLE, stable_hovered)
        _draw_button(surface, self.altered_button_rect, BUTTON_LABEL_ALTERED, altered_hovered)

        feedback_top = 250
        if self.phase == "feedback":
            feedback_surface = settings.FONTS["feedback"].render(self.feedback_message, True, self.feedback_color)
            surface.blit(feedback_surface, feedback_surface.get_rect(centerx=settings.VIRTUAL_WIDTH / 2, top=feedback_top))
        elif self.error_message is not None:
            error_surface = settings.FONTS["feedback"].render(self.error_message, True, settings.COLORS["warning"])
            surface.blit(error_surface, error_surface.get_rect(centerx=settings.VIRTUAL_WIDTH / 2, top=feedback_top))
