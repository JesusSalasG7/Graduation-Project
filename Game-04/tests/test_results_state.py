"""
Checks the results screen in isolation, entering it directly with
made-up stats (state_machine.change("results", ...)) instead of playing
a full match -- state_machine.change works from any current state
(including the initial StoryState), so this doesn't need play_game.
"""
import pygame

from gale.input_handler import KEY_r, KeyboardData
from src.states.play_state import PlayState
from src.states.results_state import ResultsState

import settings


def make_keydown(key: int) -> KeyboardData:
    event = pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="")
    return KeyboardData(event)


SAMPLE_LOG = [
    {
        "round": 1,
        "string": "RADAR",
        "player_answer": "stable",
        "correct_answer": "stable",
        "is_correct": True,
        "response_time_ms": 1200,
    },
    {
        "round": 2,
        "string": "CODIGO",
        "player_answer": "stable",
        "correct_answer": "altered",
        "is_correct": False,
        "response_time_ms": 900,
    },
]


def test_receives_and_stores_the_stats_it_is_given(game):
    game.state_machine.change(
        "results",
        game_log=SAMPLE_LOG,
        correct_count=1,
        wrong_count=1,
        score=100,
        total_time_ms=2100,
    )
    state = game.state_machine.current
    assert isinstance(state, ResultsState)
    assert state.game_log == SAMPLE_LOG
    assert state.correct_count == 1
    assert state.wrong_count == 1
    assert state.score == 100
    assert state.total_time_ms == 2100


def test_render_does_not_crash(game):
    game.state_machine.change("results", game_log=SAMPLE_LOG, correct_count=1, wrong_count=1, score=100)
    state = game.state_machine.current
    surface = pygame.Surface((settings.VIRTUAL_WIDTH, settings.VIRTUAL_HEIGHT))
    state.render(surface)  # must not raise


def test_missing_stats_default_to_empty(game):
    # ResultsState can in principle be entered directly (e.g. from a
    # future menu) without any kwargs -- it should not crash, just show
    # an empty match.
    game.state_machine.change("results")
    state = game.state_machine.current
    assert state.game_log == []
    assert state.correct_count == 0
    assert state.score == 0


def test_restart_key_starts_a_new_match(game):
    game.state_machine.change("results", game_log=SAMPLE_LOG, correct_count=1, wrong_count=1, score=100)
    state = game.state_machine.current
    assert isinstance(state, ResultsState)

    state.on_input("restart", make_keydown(KEY_r))
    assert isinstance(game.state_machine.current, PlayState)
