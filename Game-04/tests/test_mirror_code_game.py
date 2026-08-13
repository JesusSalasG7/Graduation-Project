"""
Checks MirrorCodeGame's own wiring: it starts on StoryState, "quit"
stops the loop instead of reaching the state machine, and update/render
delegate to whichever state is current without crashing.
"""
import pygame

from gale.input_handler import KEY_ESCAPE, KEY_RETURN, KeyboardData
from src.states.play_state import PlayState
from src.states.story_state import StoryState

import settings


def make_keydown(key: int) -> KeyboardData:
    event = pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="")
    return KeyboardData(event)


def test_starts_on_story_state(game):
    assert isinstance(game.state_machine.current, StoryState)


def test_confirm_eventually_advances_past_the_story(game):
    # First "confirm" fast-forwards the typewriter, the second moves on.
    game.on_input("confirm", make_keydown(KEY_RETURN))
    game.on_input("confirm", make_keydown(KEY_RETURN))
    assert isinstance(game.state_machine.current, PlayState)


def test_quit_stops_the_game(game):
    assert game.running is False  # not started via exec() in these tests
    game.running = True
    game.on_input("quit", make_keydown(KEY_ESCAPE))
    assert game.running is False


def test_update_and_render_do_not_crash(game):
    game.update(1 / 60)
    surface = pygame.Surface((settings.VIRTUAL_WIDTH, settings.VIRTUAL_HEIGHT))
    game.render(surface)  # must not raise
