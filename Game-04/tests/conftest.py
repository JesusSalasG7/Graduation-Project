"""
Runs before any test module is imported. Forces SDL's dummy video/audio
drivers so importing `settings` (which initializes pygame's display and
builds its fonts) works headlessly in CI/terminals without a screen or
sound card. Also provides fixtures shared by every test module that
needs to drive a full MirrorCodeGame instance through real input events.
"""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

import settings
from gale.input_handler import MouseClickData
from src.mirror_code_game import MirrorCodeGame


@pytest.fixture
def game():
    """A freshly started MirrorCodeGame, on its initial StoryState."""
    instance = MirrorCodeGame(
        settings.TITLE,
        settings.WINDOW_WIDTH,
        settings.WINDOW_HEIGHT,
        settings.VIRTUAL_WIDTH,
        settings.VIRTUAL_HEIGHT,
    )
    yield instance
    instance.quit()


@pytest.fixture
def press_button():
    """
    Returns a helper that simulates a real left-click at the center of a
    pygame.Rect (given in virtual canvas coordinates): builds an actual
    pygame mouse-down event, converts it to window coordinates the same
    way a real click would arrive, and feeds it through
    MirrorCodeGame.on_input -- the same path settings.py's InputHandler
    bindings and the state machine use during a real run.
    """

    def _press_button(target_game, rect: pygame.Rect) -> None:
        virtual_x, virtual_y = rect.center
        window_x = virtual_x * settings.WINDOW_WIDTH / settings.VIRTUAL_WIDTH
        window_y = virtual_y * settings.WINDOW_HEIGHT / settings.VIRTUAL_HEIGHT

        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(window_x, window_y), button=1)
        target_game.on_input("mouse_click", MouseClickData(event))

    return _press_button


@pytest.fixture
def play_game(game):
    """
    A MirrorCodeGame already past the intro, sitting on a fresh
    PlayState -- for tests that only care about round/results/game-over
    mechanics and don't need to exercise StoryState itself.
    """
    game.state_machine.change("play")
    return game
