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

        self._spawn_apple()

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
        apple = self.food_field.spawn_one(self.snake.segments, value_choices=value_choices)

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

    # ------------------------------------------------------------------
    # Mecanica "Filtro Metabolico de Valores" (Modo Desafio)
    # ------------------------------------------------------------------

    def _apple_passes_filter(self, value: int) -> bool:
        # TODO: Reto "Filtro Metabolico de Valores" -- ver Reto_Filtro_Metabolico.html
        pass

    def _handle_challenge_apple_eaten(self, apple) -> None:
        # TODO: Reto "Filtro Metabolico de Valores" -- ver Reto_Filtro_Metabolico.html
        pass
