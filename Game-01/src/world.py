"""
The game state: grid dimensions, the snake, the food, the score, and
the fixed-tick accumulator that advances the simulation one grid step
at a time. This is the model layer -- gale/pygame only ever see the
read-only state exposed here through the renderer.
"""
import random

import settings
from src import records
from src.direction import Direction
from src.entities.food import FoodField
from src.entities.snake import Snake


class World:
    def __init__(
        self, grid_cols: int, grid_rows: int, move_interval: float, mode: str = "classic"
    ) -> None:
        self.grid_cols = grid_cols
        self.grid_rows = grid_rows
        self.move_interval = move_interval
        # Fixed for the lifetime of this World (chosen at MenuState, forwarded
        # through PlayState) -- unlike the per-round state below, it is not
        # touched by reset(), same as grid_cols/grid_rows/move_interval.
        self.mode = mode
        self.reset()

    def reset(self) -> None:
        start_cell = (self.grid_cols // 2, self.grid_rows // 2)
        self.snake = Snake(start_cell, Direction.LEFT, initial_length=3)
        self.food_field = FoodField(self.grid_cols, self.grid_rows)

        # Challenge mode's active value-filter window; reset to the default
        # range every round so a past match's state never leaks into the
        # next one (see settings.CHALLENGE_FILTER_MIN_DEFAULT/MAX_DEFAULT).
        self.filter_min = settings.CHALLENGE_FILTER_MIN_DEFAULT
        self.filter_max = settings.CHALLENGE_FILTER_MAX_DEFAULT
        self._filter_reshuffle_timer = 0.0

        # Classic mode keeps the historical single apple; challenge mode
        # keeps CHALLENGE_APPLE_COUNT on the board at once -- this is the
        # array count_apples_in_range() (A01) actually counts over.
        apple_count = settings.CHALLENGE_APPLE_COUNT if self.mode == "challenge" else 1
        for _ in range(apple_count):
            self._spawn_apple()

        self._range_bonus_timer = 0.0
        self._range_bonus_event = None

        self.score = 0
        self.game_over = False
        self._move_timer = 0.0

        # Reloaded fresh every round so a record saved at the end of the
        # previous one (see PlayState's name-entry flow) is picked up
        # immediately, without requiring the app to restart.
        self.best_score = records.best_score()

        # Tongue flicks are an occasional, self-timed habit rather than
        # something triggered directly by game state: the snake waits a
        # random amount of time, flicks briefly, then picks a new wait.
        self.tongue_flicking = False
        self.tongue_progress = 0.0
        self._tongue_timer = random.uniform(*settings.TONGUE_FLICK_PAUSE_RANGE)

        # Set on a fatal collision to the cell the snake was about to
        # step into (where the impact happened), so the renderer can
        # burst animated stars there. The snake itself never actually
        # moves onto that cell -- it stops one step short of it.
        self.impact_cell = None
        self.impact_time = 0.0

        # One-shot flags for the instant a collision/eat happens, so
        # callers (e.g. to play a sound) can react exactly once instead
        # of on every frame the resulting state stays around. See
        # consume_impact_event / consume_eat_event.
        self._impact_event = False
        self._eat_event = False

    @property
    def finished(self) -> bool:
        return self.game_over

    @property
    def mouth_open(self) -> bool:
        return self._apple_nearby()

    @property
    def display_best_score(self) -> int:
        """
        The number the HUD's trophy should show. While the current run is
        at or above the saved best, this tracks the live score instead of
        the (now stale) saved value -- so it climbs in real time whether
        there was no record yet (best_score == 0) or the run just tied
        the existing one, and keeps climbing until the run ends.
        """
        return max(self.best_score, self.score)

    def consume_impact_event(self) -> bool:
        """Whether a collision just happened, cleared once read."""
        happened = self._impact_event
        self._impact_event = False
        return happened

    def consume_eat_event(self) -> bool:
        """Whether the snake just ate an apple, cleared once read."""
        happened = self._eat_event
        self._eat_event = False
        return happened

    def consume_range_bonus_event(self):
        """
        (count, bonus_points) from the last count_apples_in_range() payout,
        or None if none happened since the last read -- challenge mode only,
        see _update_range_bonus.
        """
        event = self._range_bonus_event
        self._range_bonus_event = None
        return event

    def set_direction(self, direction: Direction) -> None:
        if not self.finished:
            self.snake.set_direction(direction)

    def update(self, dt: float) -> None:
        if self.finished:
            if self.impact_cell is not None:
                self.impact_time += dt
            return

        self._update_tongue(dt)
        self._update_apple_timers(dt)

        if self.mode == "challenge":
            self._update_filter_window(dt)
            self._update_range_bonus(dt)

        self._move_timer += dt

        while self._move_timer >= self.move_interval:
            self._move_timer -= self.move_interval
            self._step()

            if self.finished:
                break

    def _update_tongue(self, dt: float) -> None:
        self._tongue_timer -= dt

        if self.tongue_flicking:
            self.tongue_progress = 1 - max(self._tongue_timer, 0) / settings.TONGUE_FLICK_DURATION

            if self._tongue_timer <= 0:
                self.tongue_flicking = False
                self._tongue_timer = random.uniform(*settings.TONGUE_FLICK_PAUSE_RANGE)
        elif self._tongue_timer <= 0:
            self.tongue_flicking = True
            self.tongue_progress = 0.0
            self._tongue_timer = settings.TONGUE_FLICK_DURATION

    def _apple_nearby(self) -> bool:
        hx, hy = self.snake.head
        range_sq = settings.APPLE_PROXIMITY_RANGE ** 2
        return any(
            (ax - hx) ** 2 + (ay - hy) ** 2 <= range_sq
            for ax, ay in (apple.position for apple in self.food_field.apples)
        )

    def _step(self) -> None:
        next_x, next_y = self.snake.next_head

        out_of_bounds = not (
            0 <= next_x < self.grid_cols and 0 <= next_y < self.grid_rows
        )

        if out_of_bounds or self.snake.would_collide_with_self((next_x, next_y)):
            # Face the direction of the hit without actually stepping
            # into the wall/its own body -- the snake stops one cell
            # short, and the impact is what the star burst marks.
            self.snake.direction = self.snake.pending_direction
            self.game_over = True
            self.impact_cell = (next_x, next_y)
            self.impact_time = 0.0
            self._impact_event = True
            return

        self.snake.move()
        eaten_apple = self.food_field.apple_at(self.snake.head)

        if eaten_apple is not None:
            if self.mode == "challenge":
                self._handle_challenge_apple_eaten(eaten_apple)
            else:
                self.snake.grow()
                self.score += 1
                self.food_field.remove(eaten_apple)
                self._spawn_apple()
                self._eat_event = True

    def _spawn_apple(self) -> None:
        """
        Spawns one apple, letting FoodField know whether to hand it a random
        challenge-mode value or leave it at the classic default of 1. Not
        part of the filtering mechanic itself -- just mode-aware plumbing --
        so it is safe to call it directly.

        In challenge mode, an apple landing outside the active filter range
        also gets armed with a random expiry (see _update_apple_timers) so
        a "poison" apple doesn't block a cell forever.
        """
        value_choices = settings.CHALLENGE_APPLE_VALUES if self.mode == "challenge" else None
        # Snake segments AND every apple already on the board -- with only
        # ever one apple at a time (classic mode) the latter was always
        # empty and didn't matter, but challenge mode keeps several apples
        # alive at once, so two of them landing on the same cell is a real
        # possibility without this.
        occupied_cells = list(self.snake.segments) + [
            apple.position for apple in self.food_field.apples
        ]
        apple = self.food_field.spawn_one(occupied_cells, value_choices=value_choices)

        if apple is not None and self.mode == "challenge" and not self._apple_passes_filter(apple.value):
            apple.expires_in = random.uniform(*settings.CHALLENGE_OUT_OF_RANGE_LIFETIME_RANGE)

    def _update_apple_timers(self, dt: float) -> None:
        """
        Ticks down expires_in on every apple that has one armed (always an
        out-of-filter-range apple in challenge mode -- see _spawn_apple)
        and replaces whichever one reaches zero. Iterates over a snapshot
        of food_field.apples since expiring one removes it from that same
        list mid-loop.
        """
        for apple in list(self.food_field.apples):
            if apple.expires_in is None:
                continue

            apple.expires_in -= dt

            if apple.expires_in <= 0:
                self.food_field.remove(apple)
                self._spawn_apple()

    def _update_filter_window(self, dt: float) -> None:
        """
        Every CHALLENGE_FILTER_RESHUFFLE_SECONDS, swaps [filter_min,
        filter_max] for a different window from settings.CHALLENGE_FILTER_
        WINDOWS -- challenge mode only (see update()). Which apples on the
        board currently pass the filter can change the instant this fires,
        so every apple's expiry timer is re-synced against the new window
        right after: freshly-out-of-range apples get one armed (same rule
        _spawn_apple uses), freshly-back-in-range ones have theirs cleared.
        """
        self._filter_reshuffle_timer += dt

        if self._filter_reshuffle_timer < settings.CHALLENGE_FILTER_RESHUFFLE_SECONDS:
            return

        self._filter_reshuffle_timer -= settings.CHALLENGE_FILTER_RESHUFFLE_SECONDS

        other_windows = [
            window
            for window in settings.CHALLENGE_FILTER_WINDOWS
            if window != (self.filter_min, self.filter_max)
        ]
        self.filter_min, self.filter_max = random.choice(other_windows)

        for apple in self.food_field.apples:
            if self._apple_passes_filter(apple.value):
                apple.expires_in = None
            elif apple.expires_in is None:
                apple.expires_in = random.uniform(*settings.CHALLENGE_OUT_OF_RANGE_LIFETIME_RANGE)

    def _update_range_bonus(self, dt: float) -> None:
        """
        Every CHALLENGE_RANGE_BONUS_INTERVAL_SECONDS, scores
        count_apples_in_range() -- challenge mode only (see update()).
        Sets _range_bonus_event so PlayState can react (a sound) exactly
        once per payout; see consume_range_bonus_event.
        """
        self._range_bonus_timer += dt

        if self._range_bonus_timer < settings.CHALLENGE_RANGE_BONUS_INTERVAL_SECONDS:
            return

        self._range_bonus_timer -= settings.CHALLENGE_RANGE_BONUS_INTERVAL_SECONDS

        # `or 0` covers count_apples_in_range() still being a TODO stub
        # (returns None) -- the bonus is simply 0 until it's implemented,
        # instead of crashing every 5 seconds.
        count = self.count_apples_in_range() or 0
        bonus = count * settings.CHALLENGE_RANGE_BONUS_PER_APPLE
        self.score += bonus
        self._range_bonus_event = (count, bonus)

    def _apple_passes_filter(self, value: int) -> bool:
        return self.filter_min <= value <= self.filter_max

    def count_apples_in_range(self) -> int:
        """
        TODO
        """
        pass

    def _handle_challenge_apple_eaten(self, apple) -> None:
        """
        Runs once, the instant the head lands on `apple`, challenge mode
        only (_step's classic-mode branch handles the other case). Safe
        apples behave like a classic-mode eat, scaled by the apple's
        value; unsafe ones behave like a fatal wall/self collision --
        same state _step sets for that, so the renderer's star burst and
        dazed face come along for free.
        """
        if self._apple_passes_filter(apple.value):
            # CHALLENGE_APPLE_VALUES includes -5, and some filter windows
            # (e.g. (-5, 5)) do let a -5 apple count as "safe" -- it still
            # shouldn't shrink the snake: Snake.grow's counter isn't meant
            # to go negative (see grow_pending in src/entities/snake.py),
            # so a "safe" negative apple costs score without costing length.
            self.snake.grow(max(0, apple.value))
            self.score += apple.value
            self.food_field.remove(apple)
            self._spawn_apple()
            self._eat_event = True
            return

        self.game_over = True
        self.impact_cell = apple.position
        self.impact_time = 0.0
        self._impact_event = True
