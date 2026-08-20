"""
Tests for src/world.py's letter resolution: judgement scoring, combo
tracking, and the lives/game-over rule.
"""
import settings
from src import scoring
from src.world import World


def test_perfect_hit_awards_points_and_builds_combo():
    world = World(travel_time=1.0, seed=1)
    letter = world.active_word.letters[0]
    world.elapsed = letter.hit_time  # land exactly on the beat

    judgement = world.handle_key(letter.char)

    assert judgement == scoring.PERFECT
    assert world.score == scoring.points_for(scoring.PERFECT)
    assert world.combo == 1
    assert world.max_combo == 1
    assert letter.resolved and letter.judgement == scoring.PERFECT


def test_correct_letter_pressed_too_early_resolves_as_miss_and_costs_a_life():
    world = World(travel_time=1.0, seed=1)
    letter = world.active_word.letters[0]
    world.combo = 4  # pretend there was already a streak going
    world.elapsed = letter.hit_time - (settings.OK_WINDOW_SECONDS + 1.0)

    judgement = world.handle_key(letter.char)

    assert judgement == scoring.MISS
    assert letter.resolved and letter.judgement == scoring.MISS
    assert world.combo == 0
    assert world.lives == settings.STARTING_LIVES - 1
    assert world.score == 0


def test_wrong_letter_resolves_as_miss_and_costs_a_life():
    world = World(travel_time=1.0, seed=1)
    letter = world.active_word.letters[0]
    world.combo = 4  # pretend there was already a streak going
    world.elapsed = letter.hit_time  # perfectly on time -- only the character is wrong

    wrong_char = next(c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if c != letter.char)
    judgement = world.handle_key(wrong_char)

    assert judgement == scoring.MISS
    assert letter.resolved and letter.judgement == scoring.MISS
    assert world.combo == 0
    assert world.lives == settings.STARTING_LIVES - 1


def test_missed_letter_resets_combo_and_costs_a_life():
    world = World(travel_time=1.0, seed=1)
    letter = world.active_word.letters[0]
    world.combo = 4  # pretend there was already a streak going

    world.elapsed = letter.hit_time + settings.OK_WINDOW_SECONDS + 0.001
    world.update(0.0)  # drives the auto-miss expiry check

    assert letter.judgement == scoring.MISS
    assert world.combo == 0
    assert world.lives == settings.STARTING_LIVES - 1


def test_game_over_once_lives_run_out():
    world = World(travel_time=1.0, seed=1)
    world.lives = 1
    letter = world.active_word.letters[0]

    world.elapsed = letter.hit_time + settings.OK_WINDOW_SECONDS + 0.001
    world.update(0.0)

    assert world.lives == 0
    assert world.game_over is True
    # The word active at the moment of game over must stay put -- a
    # regression here previously let a miss that also completed the
    # word spawn a *new* one the instant after the run had ended.
    assert world.active_word.letters[0] is letter


def test_only_one_letter_is_pending_at_a_time():
    world = World(travel_time=1.0, seed=1)
    word = world.active_word

    # Force a word with at least 3 letters so there's something to walk
    # through beyond just "the first one" -- WordStream(seed=1)'s first
    # word already satisfies this, but assert it so the test stays
    # meaningful if that ever changes.
    assert len(word.letters) >= 3

    for _ in range(len(word.letters)):
        pending = [l for l in word.letters if l.is_pending]
        assert len(pending) == 1, "more than one letter was falling at once"

        letter = pending[0]
        world.elapsed = letter.hit_time  # land exactly on the beat
        judgement = world.handle_key(letter.char)
        assert judgement == scoring.PERFECT

    assert word.complete
    assert not any(l.is_pending for l in word.letters)


def test_next_letter_only_starts_after_the_previous_one_resolves():
    world = World(travel_time=1.0, seed=1)
    word = world.active_word
    assert len(word.letters) >= 2

    second_letter = word.letters[1]
    assert not second_letter.started
    assert second_letter.hit_time is None

    first_letter = word.letters[0]
    world.elapsed = first_letter.hit_time
    world.handle_key(first_letter.char)

    assert second_letter.started
    assert second_letter.hit_time == world.elapsed + world.travel_time


def test_accuracy_percent_is_100_before_anything_resolves():
    world = World(travel_time=1.0, seed=1)
    assert world.accuracy_percent == 100.0


def test_accuracy_percent_reflects_weighted_judgements():
    world = World(travel_time=1.0, seed=1)
    letter = world.active_word.letters[0]
    world.elapsed = letter.hit_time
    world.handle_key(letter.char)  # a Perfecto -> full weight

    assert world.accuracy_percent == 100.0

    # A miss on the next pending letter should drag accuracy down from 100.
    next_letter = next(l for l in world.active_word.letters if l.is_pending)
    world.elapsed = next_letter.hit_time + settings.OK_WINDOW_SECONDS + 0.001
    world.update(0.0)

    assert 0.0 < world.accuracy_percent < 100.0


def test_upcoming_words_stays_filled_and_advances_with_the_active_word():
    world = World(travel_time=1.0, seed=1)
    assert len(world.upcoming_words) == settings.WORD_LOOKAHEAD_COUNT

    next_word = world.upcoming_words[0]

    # Resolving every letter (the last one included) is what triggers
    # World to move on to the next word -- see World._resolve_letter /
    # _finish_word.
    for letter in world.active_word.letters:
        world._resolve_letter(letter, scoring.OK)

    assert world.active_word.text == next_word
    assert len(world.upcoming_words) == settings.WORD_LOOKAHEAD_COUNT
