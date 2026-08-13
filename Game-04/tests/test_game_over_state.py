"""
Checks the game-over screen reached when a round's countdown hits zero
(see test_play_state.py::test_running_out_of_time_triggers_game_over):
the explosion animation runs for its full duration, restart is ignored
until it's done, and then it drops the player back into a fresh match.
"""
import pygame

from gale.input_handler import KEY_r, KeyboardData
from src.states.game_over_state import EXPLOSION_DURATION, GameOverState
from src.states.play_state import PlayState, TIME_LIMIT

import settings


def make_keydown(key: int) -> KeyboardData:
    event = pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="")
    return KeyboardData(event)


def _blow_up(play_game) -> GameOverState:
    play_game.update(TIME_LIMIT + 0.1)
    state = play_game.state_machine.current
    assert isinstance(state, GameOverState)
    return state


def test_starts_exploding_with_particles(play_game):
    state = _blow_up(play_game)
    assert state.phase == "exploding"
    assert len(state.particles) > 0


def test_restart_is_ignored_while_exploding(play_game):
    state = _blow_up(play_game)
    state.on_input("restart", make_keydown(KEY_r))
    assert isinstance(play_game.state_machine.current, GameOverState)
    assert state.phase == "exploding"


def test_explosion_ends_after_its_duration(play_game):
    state = _blow_up(play_game)
    play_game.update(EXPLOSION_DURATION + 0.1)
    assert state.phase == "over"


def test_restart_after_explosion_starts_a_fresh_match(play_game):
    state = _blow_up(play_game)
    play_game.update(EXPLOSION_DURATION + 0.1)

    state.on_input("restart", make_keydown(KEY_r))
    new_state = play_game.state_machine.current
    assert isinstance(new_state, PlayState)
    assert new_state.time_remaining == TIME_LIMIT


def test_render_does_not_crash_exploding_and_over(play_game):
    state = _blow_up(play_game)
    surface = pygame.Surface((settings.VIRTUAL_WIDTH, settings.VIRTUAL_HEIGHT))
    state.render(surface)  # must not raise, mid-explosion

    play_game.update(EXPLOSION_DURATION + 0.1)
    state.render(surface)  # must not raise, GAME OVER screen
