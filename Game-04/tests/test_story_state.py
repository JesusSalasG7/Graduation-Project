"""
Checks the intro screen: the typewriter reveal, that a click/keypress
fast-forwards it instead of skipping straight past the story, and that
a second confirm (once fully revealed) moves on to PlayState.
"""
import pygame

from src.states.play_state import PlayState
from src.states.story_state import STORY_LINES, StoryState

import settings


def test_starts_with_nothing_revealed(game):
    state = game.state_machine.current
    assert isinstance(state, StoryState)
    assert state._revealed_chars() == 0
    assert not state._fully_revealed()


def test_time_reveals_characters_progressively(game):
    state = game.state_machine.current
    game.update(0.2)
    revealed_early = state._revealed_chars()
    assert 0 < revealed_early < state.total_chars

    game.update(10.0)
    assert state._fully_revealed()


def test_first_confirm_fast_forwards_instead_of_advancing(game, press_button):
    state = game.state_machine.current
    game.update(0.05)  # only a handful of characters revealed so far
    assert not state._fully_revealed()

    press_button(game, pygame.Rect(0, 0, settings.VIRTUAL_WIDTH, settings.VIRTUAL_HEIGHT))

    assert state._fully_revealed()
    # Still on the story screen -- the first confirm only finished the
    # typewriter, it didn't move on yet.
    assert isinstance(game.state_machine.current, StoryState)


def test_second_confirm_advances_to_play(game, press_button):
    click_anywhere = pygame.Rect(0, 0, settings.VIRTUAL_WIDTH, settings.VIRTUAL_HEIGHT)
    press_button(game, click_anywhere)  # finishes the typewriter
    press_button(game, click_anywhere)  # advances

    assert isinstance(game.state_machine.current, PlayState)


def test_render_does_not_crash_mid_typing_and_fully_revealed(game):
    state = game.state_machine.current
    surface = pygame.Surface((settings.VIRTUAL_WIDTH, settings.VIRTUAL_HEIGHT))

    game.update(0.05)
    state.render(surface)  # must not raise, mid-typewriter

    game.update(10.0)
    state.render(surface)  # must not raise, fully revealed (+ blinking cursor)


def test_story_text_is_non_empty():
    assert any(line.strip() for line in STORY_LINES)
