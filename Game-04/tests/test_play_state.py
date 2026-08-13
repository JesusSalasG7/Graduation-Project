"""
Drives a real MirrorCodeGame through PlayState via actual gale input
events (see tests/conftest.py's press_button/play_game fixtures):
round/word setup, scoring, the per-round countdown, and the game-over
transition when that countdown reaches zero.
"""
from src.signal_check import is_stable_signal
from src.states.game_over_state import GameOverState
from src.states.play_state import FEEDBACK_DURATION, PlayState, TIME_LIMIT, TOTAL_ROUNDS, WORD_POOL
from src.states.results_state import ResultsState


def test_first_round_shows_a_word_from_the_pool(play_game):
    state = play_game.state_machine.current
    assert isinstance(state, PlayState)
    assert state.current_string in WORD_POOL
    assert state.current_round == 1
    assert state.phase == "waiting"


def test_a_match_draws_total_rounds_distinct_words(play_game):
    state = play_game.state_machine.current
    assert len(state.round_strings) == TOTAL_ROUNDS
    assert len(set(state.round_strings)) == TOTAL_ROUNDS
    assert all(word in WORD_POOL for word in state.round_strings)


def test_round_starts_with_the_full_time_limit(play_game):
    state = play_game.state_machine.current
    assert state.time_remaining == TIME_LIMIT


def test_time_remaining_counts_down_while_waiting(play_game):
    state = play_game.state_machine.current
    play_game.update(1.5)
    assert state.time_remaining == TIME_LIMIT - 1.5


def test_answering_correctly_scores_and_logs_the_round(play_game, press_button):
    state = play_game.state_machine.current
    correct_button_is_stable = is_stable_signal(state.current_string)
    rect = state.stable_button_rect if correct_button_is_stable else state.altered_button_rect
    press_button(play_game, rect)

    assert state.phase == "feedback"
    assert state.correct_count == 1
    assert state.score == 100
    assert state.game_log[-1]["is_correct"] is True


def test_answering_wrong_does_not_score(play_game, press_button):
    state = play_game.state_machine.current
    correct_button_is_stable = is_stable_signal(state.current_string)
    # Deliberately press the OTHER button.
    rect = state.altered_button_rect if correct_button_is_stable else state.stable_button_rect
    press_button(play_game, rect)

    assert state.wrong_count == 1
    assert state.correct_count == 0
    assert state.score == 0
    assert state.game_log[-1]["is_correct"] is False


def test_game_log_entry_has_the_expected_shape(play_game, press_button):
    state = play_game.state_machine.current
    press_button(play_game, state.stable_button_rect)
    entry = state.game_log[0]
    assert set(entry.keys()) == {
        "round",
        "string",
        "player_answer",
        "correct_answer",
        "is_correct",
        "response_time_ms",
    }
    assert isinstance(entry["response_time_ms"], int)
    assert entry["response_time_ms"] >= 0


def test_click_during_feedback_is_ignored(play_game, press_button):
    state = play_game.state_machine.current
    press_button(play_game, state.stable_button_rect)
    assert state.phase == "feedback"
    assert len(state.game_log) == 1

    # A second click before the feedback delay elapses must not score
    # a second round on top of the first one.
    press_button(play_game, state.altered_button_rect)
    assert len(state.game_log) == 1


def test_answering_every_round_in_time_reaches_results(play_game, press_button):
    for _ in range(TOTAL_ROUNDS):
        state = play_game.state_machine.current
        assert isinstance(state, PlayState)
        correct_button_is_stable = is_stable_signal(state.current_string)
        rect = state.stable_button_rect if correct_button_is_stable else state.altered_button_rect
        press_button(play_game, rect)
        play_game.update(FEEDBACK_DURATION + 0.01)

    final_state = play_game.state_machine.current
    assert isinstance(final_state, ResultsState)
    assert final_state.correct_count == TOTAL_ROUNDS
    assert len(final_state.game_log) == TOTAL_ROUNDS


def test_running_out_of_time_triggers_game_over(play_game):
    play_game.update(TIME_LIMIT + 0.1)

    game_over_state = play_game.state_machine.current
    assert isinstance(game_over_state, GameOverState)
    assert game_over_state.phase == "exploding"


def test_restart_after_results_starts_a_fresh_match(play_game, press_button):
    for _ in range(TOTAL_ROUNDS):
        state = play_game.state_machine.current
        correct_button_is_stable = is_stable_signal(state.current_string)
        rect = state.stable_button_rect if correct_button_is_stable else state.altered_button_rect
        press_button(play_game, rect)
        play_game.update(FEEDBACK_DURATION + 0.01)

    assert isinstance(play_game.state_machine.current, ResultsState)

    play_game.state_machine.change("play")
    new_state = play_game.state_machine.current
    assert isinstance(new_state, PlayState)
    assert new_state.current_round == 1
    assert new_state.score == 0
    assert new_state.time_remaining == TIME_LIMIT
