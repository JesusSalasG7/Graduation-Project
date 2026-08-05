"""
The function must walk self.food_field.apples and return how many of
them have a value inside [self.filter_min, self.filter_max] (inclusive),
using the already-implemented self._apple_passes_filter(apple.value)
as the per-apple test.
"""
import pytest

from src.entities.food import Apple
from src.world import World


def make_world() -> World:
    """A challenge-mode World with its randomly spawned apples cleared,
    so each test can install its own deterministic set."""
    world = World(grid_cols=20, grid_rows=15, move_interval=0.15, mode="challenge")
    world.food_field.apples.clear()
    return world


def set_apples(world: World, values) -> None:
    world.food_field.apples = [Apple((i, 0), value=v) for i, v in enumerate(values)]


def test_example_from_challenge_doc_window_0_10():
    world = make_world()
    set_apples(world, [-5, 5, 15, 5, -5, 15])
    world.filter_min, world.filter_max = 0, 10
    assert world.count_apples_in_range() == 2  # the two +5s


def test_example_from_challenge_doc_window_neg5_5():
    world = make_world()
    set_apples(world, [-5, 5, 15, 5, -5, 15])
    world.filter_min, world.filter_max = -5, 5
    assert world.count_apples_in_range() == 4  # the two -5s and two +5s


def test_example_from_challenge_doc_window_neg5_15():
    world = make_world()
    set_apples(world, [-5, 5, 15, 5, -5, 15])
    world.filter_min, world.filter_max = -5, 15
    assert world.count_apples_in_range() == 6  # all of them


def test_example_from_challenge_doc_window_10_20():
    world = make_world()
    set_apples(world, [-5, 5, 15, 5, -5, 15])
    world.filter_min, world.filter_max = 10, 20
    assert world.count_apples_in_range() == 2  # the two +15s


def test_no_apples_on_board():
    world = make_world()
    world.filter_min, world.filter_max = 0, 10
    assert world.count_apples_in_range() == 0


def test_no_apples_pass_the_filter():
    world = make_world()
    set_apples(world, [-5, -5, 15, 15])
    world.filter_min, world.filter_max = 0, 10
    assert world.count_apples_in_range() == 0


def test_all_apples_pass_the_filter():
    world = make_world()
    set_apples(world, [5, 5, 5])
    world.filter_min, world.filter_max = 0, 10
    assert world.count_apples_in_range() == 3


def test_bounds_are_inclusive():
    world = make_world()
    set_apples(world, [0, 10, -1, 11])
    world.filter_min, world.filter_max = 0, 10
    assert world.count_apples_in_range() == 2  # exactly 0 and exactly 10 count


def test_does_not_mutate_the_apple_list():
    world = make_world()
    set_apples(world, [-5, 5, 15])
    world.filter_min, world.filter_max = 0, 10
    world.count_apples_in_range()
    assert len(world.food_field.apples) == 3


@pytest.mark.parametrize(
    "values, window, expected",
    [
        ([5], (0, 10), 1),
        ([-5], (0, 10), 0),
        ([-5, 5, 15] * 10, (-5, 15), 30),
    ],
)
def test_various_boards(values, window, expected):
    world = make_world()
    set_apples(world, values)
    world.filter_min, world.filter_max = window
    assert world.count_apples_in_range() == expected
