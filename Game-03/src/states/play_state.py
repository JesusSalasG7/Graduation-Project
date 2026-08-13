"""
Main state of the Rubik's Cube simulation: draws the cube in a real 3D
projection, centered on screen, and controls it via keyboard (layer
turns, see `_register_keyboard_shortcuts`, animated -- see
`_MoveInProgress`) or by dragging it with the mouse to orbit the
camera (src.view_3d).
"""
import math
import random
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

import pygame

from gale.conf import settings
from gale.input_handler import (
    InputData,
    InputHandler,
    KeyboardData,
    MouseClickData,
    MouseMotionData,
    MOD_ALT,
    MOD_SHIFT,
    KEY_b,
    KEY_d,
    KEY_DOWN,
    KEY_e,
    KEY_f,
    KEY_l,
    KEY_LEFT,
    KEY_m,
    KEY_r,
    KEY_RIGHT,
    KEY_s,
    KEY_u,
    KEY_UP,
)
from gale.state import BaseState

from src.rubik_cube import Position, RubikCube, ALL_MOVES, inverse_move, layers_for_move
from src.view_3d import LayerAnimation, draw_cube_3d, draw_face_guide

COLOR_BG = pygame.Color(225, 225, 228)

CUBE_SCALE = 28.0

DRAG_SENSITIVITY = 0.012
KEYBOARD_ROTATION_SPEED = math.radians(120)  # radians per second, while the arrow key is held
MAX_PITCH = math.radians(80)

MOVE_ANIMATION_DURATION = 0.18  # seconds a 90-degree turn takes to animate, turned by hand
SCRAMBLE_ANIMATION_DURATION = 0.09  # faster than by hand, so scrambling feels snappy without being a flash
SCRAMBLE_MOVE_COUNT = 20

INITIAL_YAW = math.radians(-35)
INITIAL_PITCH = math.radians(25)

# --- "Shuffle" button (shuffle.png), top center of the screen ----------
SHUFFLE_ICON_SIZE = 18
SHUFFLE_BUTTON_SIZE = 28
SHUFFLE_BUTTON_TOP_MARGIN = 6
SHUFFLE_BUTTON_LEFT_MARGIN = 6
SHUFFLING_ICON_SPIN_SPEED = math.radians(360)  # the icon spins while shuffling is in progress

SHUFFLE_BUTTON_COLOR = pygame.Color(255, 255, 255)
SHUFFLE_BUTTON_HOVER_COLOR = pygame.Color(210, 225, 250)
SHUFFLE_BUTTON_BORDER_COLOR = pygame.Color(170, 170, 178)

# --- "Auto" button (auto.png), next to "Shuffle": the *only* button
# that starts the scramble timer (see `_activate_auto`) -- it scrambles
# the cube exactly like "Shuffle" does, but also (re)starts the timer
# at 00:00. Plain "Shuffle" never touches the timer, so scrambling by
# hand doesn't time anything.
AUTO_ICON_SIZE = 18
AUTO_BUTTON_SIZE = 28
GAP_BETWEEN_SHUFFLE_AND_AUTO_BUTTONS = 6

AUTO_BUTTON_COLOR = pygame.Color(255, 255, 255)
AUTO_BUTTON_HOVER_COLOR = pygame.Color(210, 225, 250)
AUTO_BUTTON_ACTIVE_COLOR = pygame.Color(180, 250, 195)  # while the timer is running
AUTO_BUTTON_BORDER_COLOR = pygame.Color(170, 170, 178)

# --- "Eye" button (eye_open.png/eye_closed.png), next to "Auto": toggles
# the face guide (see `draw_face_guide` in src/view_3d.py), which marks
# on the cube which face is U/D/L/R/F/B.
EYE_ICON_SIZE = 16
EYE_BUTTON_SIZE = 28
GAP_BETWEEN_AUTO_AND_EYE_BUTTONS = 6

EYE_BUTTON_COLOR = pygame.Color(255, 255, 255)
EYE_BUTTON_HOVER_COLOR = pygame.Color(210, 225, 250)
EYE_BUTTON_ACTIVE_COLOR = pygame.Color(255, 232, 175)
EYE_BUTTON_BORDER_COLOR = pygame.Color(170, 170, 178)

# --- "Search" button (search.png), next to the "Eye" one: runs the
# A03 challenge (see src/algorithm.py::find_3d_pattern) against the
# cube's current state, looking for the 2x2x2 corner block captured
# from the solved cube in `enter` (`self._target_pattern`), and
# highlights it in 3D if it's still found intact somewhere.
SEARCH_ICON_SIZE = 16
SEARCH_BUTTON_SIZE = 28
GAP_BETWEEN_EYE_AND_SEARCH_BUTTONS = 6

SEARCH_BUTTON_COLOR = pygame.Color(255, 255, 255)
SEARCH_BUTTON_HOVER_COLOR = pygame.Color(210, 225, 250)
SEARCH_BUTTON_FOUND_COLOR = pygame.Color(200, 236, 205)
SEARCH_BUTTON_NOT_FOUND_COLOR = pygame.Color(250, 205, 205)
SEARCH_BUTTON_BORDER_COLOR = pygame.Color(170, 170, 178)

# Corner (origin_x, origin_y, origin_z) of the 2x2x2 block captured as
# the search target -- see `_target_pattern` in `enter`.
SEARCH_BLOCK_ORIGIN: Tuple[int, int, int] = (0, 0, 0)
SEARCH_BLOCK_SIZE = 2

# --- "Undo"/"Redo" buttons (undo.png/redo.png), next to "Search":
# step back and forward through the moves actually applied to the
# cube (see `_undo_stack`/`_redo_stack`, `_undo`, `_redo`).
UNDO_ICON_SIZE = 16
UNDO_BUTTON_SIZE = 28
GAP_BETWEEN_SEARCH_AND_UNDO_BUTTONS = 6
GAP_BETWEEN_UNDO_AND_REDO_BUTTONS = 4

HISTORY_BUTTON_COLOR = pygame.Color(255, 255, 255)
HISTORY_BUTTON_HOVER_COLOR = pygame.Color(210, 225, 250)
HISTORY_BUTTON_BORDER_COLOR = pygame.Color(170, 170, 178)
HISTORY_BUTTON_DISABLED_ICON_ALPHA = 80  # out of 255, how faint the icon looks when there's nothing to undo/redo

# --- Scramble timer, bottom-right corner --------------------------------
# Hidden entirely until "Auto" is pressed for the first time (see
# `_activate_auto`); from then on it counts and freezes automatically
# the first time the cube is solved again (see `_advance_timer`) -- so
# it always measures "time since the last Auto-triggered scramble",
# with no manual start/stop needed. Plain "Shuffle" never starts it.
TIMER_TEXT_SCALE = 2
TIMER_PANEL_PADDING_X = 6
TIMER_PANEL_PADDING_Y = 4
TIMER_RIGHT_MARGIN = 6
TIMER_BOTTOM_MARGIN = 6

TIMER_BG_COLOR = pygame.Color(24, 26, 33)  # dark "LCD" panel, unlike the light buttons -- reads as its own widget
TIMER_BORDER_COLOR = pygame.Color(170, 170, 178)
TIMER_SOLVED_BORDER_COLOR = pygame.Color(120, 220, 140)  # border flashes green once solved, alongside the digits
TIMER_RUNNING_TEXT_COLOR = (110, 255, 150)  # bright "LCD green" while counting
TIMER_SOLVED_TEXT_COLOR = (255, 255, 255)  # frozen at solve time, brought back to full white to stand out

# Which key triggers each outer layer (they have a wide-layer variant,
# "Xw") and each inner layer (M/E/S, no wide variant: they're already
# the middle layer). See `_register_keyboard_shortcuts`.
_KEY_BY_OUTER_LAYER: Dict[int, str] = {
    KEY_u: "U",
    KEY_d: "D",
    KEY_r: "R",
    KEY_l: "L",
    KEY_f: "F",
    KEY_b: "B",
}
_KEY_BY_INNER_LAYER: Dict[int, str] = {
    KEY_m: "M",
    KEY_e: "E",
    KEY_s: "S",
}

_VALID_MOVES = frozenset(ALL_MOVES)

_CAMERA_ACTION_LEFT = "camera_left"
_CAMERA_ACTION_RIGHT = "camera_right"
_CAMERA_ACTION_UP = "camera_up"
_CAMERA_ACTION_DOWN = "camera_down"
_CAMERA_ACTIONS = frozenset(
    {_CAMERA_ACTION_LEFT, _CAMERA_ACTION_RIGHT, _CAMERA_ACTION_UP, _CAMERA_ACTION_DOWN}
)


@dataclass
class _MoveInProgress:
    """
    A layer turn currently being animated: while it lasts, `self.cube`
    does NOT yet reflect this move (`matrix`/`colors` are only updated
    once `progress` reaches 1.0, see `_advance_move_in_progress`) --
    the only thing that changes frame to frame is `progress`, which
    `render` uses to build the `LayerAnimation` that visually rotates
    the layer in `view_3d`.

    `duration` belongs to each move (not a global constant) so a
    manual turn (`MOVE_ANIMATION_DURATION`) and one queued by
    "Shuffle" (`SCRAMBLE_ANIMATION_DURATION`, faster) can coexist
    without stepping on each other.

    `record_in_history` is False for moves that shouldn't leave an
    undo/redo trace:
        - `_undo`/`_redo` moves: those already update `_undo_stack`/
          `_redo_stack` themselves (see those methods), so
          `_advance_move_in_progress` must skip its usual "push onto
          undo, clear redo" bookkeeping for them -- otherwise undoing
          a move would immediately re-record itself as a new move and
          wipe the very redo entry it just created.
        - "Shuffle" moves (see `_continue_move_queue`): scrambling
          resets the undo/redo history instead of feeding it move by
          move (see `_shuffle`), so the scramble itself is never
          undoable -- only moves made after it are.
    """

    name: str
    axis: str
    indices: FrozenSet[int]
    clockwise: bool
    duration: float = MOVE_ANIMATION_DURATION
    progress: float = 0.0
    record_in_history: bool = True


class PlayState(BaseState):
    def enter(self, *args: Tuple[Any], **kwargs: Dict[str, Any]) -> None:
        self.cube = RubikCube()
        self._register_keyboard_shortcuts()

        # A03 search target: the 2x2x2 block of piece ids at a fixed
        # corner of the *solved* cube, captured once here before any
        # move happens. Searching for it later (see
        # `_search_for_block`) checks whether those same 8 pieces are
        # still sitting together in that exact corner-shaped block --
        # true right after this line, not guaranteed anymore once the
        # cube gets scrambled or turned.
        origin_x, origin_y, origin_z = SEARCH_BLOCK_ORIGIN
        self._target_pattern = self.cube.extract_block(
            origin_x, origin_y, origin_z, SEARCH_BLOCK_SIZE, SEARCH_BLOCK_SIZE, SEARCH_BLOCK_SIZE
        )

        # --- 3D view state (rotation) ------------------------------------
        self.yaw = INITIAL_YAW
        self.pitch = INITIAL_PITCH
        self.dragging = False
        self._last_mouse_pos: Optional[Tuple[float, float]] = None

        # Which camera arrows are currently held down: updated in
        # on_input (on press/release) and applied every frame in
        # update(), so rotation is continuous and smooth while the key
        # is held, instead of a single jump per keydown event.
        self._camera_keys_held: Dict[str, bool] = {
            action: False for action in _CAMERA_ACTIONS
        }

        # Layer turn currently being animated, or None if the cube is
        # at rest. While there is one, new moves from the keyboard are
        # ignored until it finishes (see `_start_move`) -- so there's
        # never two overlapping turns, nor a layer mid-animation
        # getting interrupted by another one.
        self._move_in_progress: Optional[_MoveInProgress] = None

        # --- "Shuffle" button ---------------------------------------------
        self._move_queue: List[str] = []  # shuffle moves still left to animate, in order
        self._shuffling = False  # True from the moment "Shuffle" is pressed until the last move is animated
        self._shuffle_icon_angle = 0.0  # spins while _shuffling is True, see update()

        self._shuffle_icon = pygame.transform.smoothscale(
            settings.TEXTURES["shuffle"].convert_alpha(), (SHUFFLE_ICON_SIZE, SHUFFLE_ICON_SIZE)
        )
        self._shuffle_button_rect = pygame.Rect(0, 0, SHUFFLE_BUTTON_SIZE, SHUFFLE_BUTTON_SIZE)
        self._shuffle_button_rect.left = SHUFFLE_BUTTON_LEFT_MARGIN
        self._shuffle_button_rect.top = SHUFFLE_BUTTON_TOP_MARGIN

        # --- "Auto" button (scramble + timer) -------------------------------
        self._auto_icon = pygame.transform.smoothscale(
            settings.TEXTURES["auto"].convert_alpha(), (AUTO_ICON_SIZE, AUTO_ICON_SIZE)
        )
        self._auto_button_rect = pygame.Rect(0, 0, AUTO_BUTTON_SIZE, AUTO_BUTTON_SIZE)
        self._auto_button_rect.left = self._shuffle_button_rect.right + GAP_BETWEEN_SHUFFLE_AND_AUTO_BUTTONS
        self._auto_button_rect.top = self._shuffle_button_rect.top

        # --- "Eye" button (face guide) -------------------------------------
        self._face_guide_active = False  # True while the eye is "open": see _draw_eye_button/render

        self._eye_open_icon = pygame.transform.smoothscale(
            settings.TEXTURES["eye_open"].convert_alpha(), (EYE_ICON_SIZE, EYE_ICON_SIZE)
        )
        self._eye_closed_icon = pygame.transform.smoothscale(
            settings.TEXTURES["eye_closed"].convert_alpha(), (EYE_ICON_SIZE, EYE_ICON_SIZE)
        )
        self._guide_font = settings.FONTS["guide"]

        self._eye_button_rect = pygame.Rect(0, 0, EYE_BUTTON_SIZE, EYE_BUTTON_SIZE)
        self._eye_button_rect.left = self._auto_button_rect.right + GAP_BETWEEN_AUTO_AND_EYE_BUTTONS
        self._eye_button_rect.top = self._shuffle_button_rect.top

        # --- "Search" button (A03) -----------------------------------------
        self._search_highlight: Optional[FrozenSet[Position]] = None  # positions to outline in draw_cube_3d
        self._search_found: Optional[bool] = None  # None: never searched yet; see _draw_search_button

        self._search_icon = pygame.transform.smoothscale(
            settings.TEXTURES["search"].convert_alpha(), (SEARCH_ICON_SIZE, SEARCH_ICON_SIZE)
        )

        self._search_button_rect = pygame.Rect(0, 0, SEARCH_BUTTON_SIZE, SEARCH_BUTTON_SIZE)
        self._search_button_rect.left = self._eye_button_rect.right + GAP_BETWEEN_EYE_AND_SEARCH_BUTTONS
        self._search_button_rect.top = self._eye_button_rect.top

        # --- "Undo"/"Redo" buttons -------------------------------------------
        # Moves actually applied to `self.cube` (oldest first); `_undo`
        # pops from here, applies the inverse, and pushes the original
        # move onto `_redo_stack`. Any new move made "for real" (manual,
        # shuffle, or `_redo`) clears `_redo_stack` -- see
        # `_advance_move_in_progress` -- since it makes the undone
        # future invalid.
        self._undo_stack: List[str] = []
        self._redo_stack: List[str] = []

        self._undo_icon = pygame.transform.smoothscale(
            settings.TEXTURES["undo"].convert_alpha(), (UNDO_ICON_SIZE, UNDO_ICON_SIZE)
        )
        self._redo_icon = pygame.transform.smoothscale(
            settings.TEXTURES["redo"].convert_alpha(), (UNDO_ICON_SIZE, UNDO_ICON_SIZE)
        )
        # Faded copies drawn instead while there's nothing to undo/redo
        # (see `_draw_history_button`), so the buttons read as disabled
        # without needing separate artwork.
        dim = (255, 255, 255, HISTORY_BUTTON_DISABLED_ICON_ALPHA)
        self._undo_icon_dimmed = self._undo_icon.copy()
        self._undo_icon_dimmed.fill(dim, special_flags=pygame.BLEND_RGBA_MULT)
        self._redo_icon_dimmed = self._redo_icon.copy()
        self._redo_icon_dimmed.fill(dim, special_flags=pygame.BLEND_RGBA_MULT)

        self._undo_button_rect = pygame.Rect(0, 0, UNDO_BUTTON_SIZE, UNDO_BUTTON_SIZE)
        self._undo_button_rect.left = self._search_button_rect.right + GAP_BETWEEN_SEARCH_AND_UNDO_BUTTONS
        self._undo_button_rect.top = self._search_button_rect.top

        self._redo_button_rect = pygame.Rect(0, 0, UNDO_BUTTON_SIZE, UNDO_BUTTON_SIZE)
        self._redo_button_rect.left = self._undo_button_rect.right + GAP_BETWEEN_UNDO_AND_REDO_BUTTONS
        self._redo_button_rect.top = self._undo_button_rect.top

        # --- Scramble timer ---------------------------------------------
        self._timer_font = settings.FONTS["timer"]
        self._timer_pending_start = False  # True while waiting for the Auto-triggered scramble to finish
        self._timer_started = False  # True once the timer has actually started counting, see `_continue_move_queue`
        self._timer_running = False  # counting right now, see `_advance_timer`
        self._timer_elapsed = 0.0  # seconds, frozen once the cube is solved again

    def exit(self) -> None:
        pass

    # --- Keyboard shortcuts --------------------------------------------------

    def _register_keyboard_shortcuts(self) -> None:
        """
        Binds each move key to its cube notation (see
        `apply_move` in src/rubik_cube.py):
            - Alone: turns that layer clockwise (e.g. key 'r' -> "R").
            - + Shift: counterclockwise (e.g. Shift+'r' -> "R'").
            - + Alt (only U/D/L/R/F/B): wide layer, the outer one
              together with its adjacent inner layer (e.g. Alt+'u' -> "Uw").
            - + Alt+Shift: counterclockwise wide layer (e.g.
              Alt+Shift+'u' -> "Uw'").
        The arrow keys orbit the camera around the cube (they don't
        turn any layer).

        Design note: the original request wanted held Shift (uppercase)
        to trigger the Y wide-layer turn, while also having Shift
        reverse the turn direction -- two uses of the same physical
        key that can't coexist in a single keyboard event. This was
        resolved by keeping Shift for reversing direction (the request
        also asks for that, more specifically, under the
        "counterclockwise modifier" point) and using a different
        modifier for the wide layer -- Alt instead of Ctrl (used
        originally): Ctrl is prone to firing by accident (system
        shortcuts, keyboard reflexes), Alt is touched by accident much
        less.
        """
        for key, name in _KEY_BY_OUTER_LAYER.items():
            InputHandler.set_keyboard_action(key, name)
            InputHandler.set_keyboard_action(key, name + "'", modifiers=MOD_SHIFT)
            InputHandler.set_keyboard_action(key, name + "w", modifiers=MOD_ALT)
            InputHandler.set_keyboard_action(
                key, name + "w'", modifiers=MOD_ALT | MOD_SHIFT
            )

        for key, name in _KEY_BY_INNER_LAYER.items():
            InputHandler.set_keyboard_action(key, name)
            InputHandler.set_keyboard_action(key, name + "'", modifiers=MOD_SHIFT)

        InputHandler.set_keyboard_action(KEY_LEFT, _CAMERA_ACTION_LEFT)
        InputHandler.set_keyboard_action(KEY_RIGHT, _CAMERA_ACTION_RIGHT)
        InputHandler.set_keyboard_action(KEY_UP, _CAMERA_ACTION_UP)
        InputHandler.set_keyboard_action(KEY_DOWN, _CAMERA_ACTION_DOWN)

    def _start_move(
        self,
        move_name: str,
        duration: float = MOVE_ANIMATION_DURATION,
        record_in_history: bool = True,
    ) -> None:
        """
        Starts the animation of a layer turn (see `_MoveInProgress`).
        The move is not applied to `self.cube` yet -- that happens
        only once the animation finishes, in
        `_advance_move_in_progress`.

        :param record_in_history: False for moves that shouldn't leave an undo/redo trace (started by `_undo`/`_redo`, or queued by `_shuffle`) -- see `_MoveInProgress`.
        """
        if self._move_in_progress is not None:
            return

        # Once the cube starts changing again, the last search result
        # no longer describes its current state -- clear it so the
        # button and the 3D highlight don't show stale information.
        self._search_highlight = None
        self._search_found = None

        axis, indices, clockwise = layers_for_move(move_name)
        self._move_in_progress = _MoveInProgress(
            name=move_name,
            axis=axis,
            indices=frozenset(indices),
            clockwise=clockwise,
            duration=duration,
            record_in_history=record_in_history,
        )

    def _advance_move_in_progress(self, dt: float) -> None:
        """If a turn is being animated, advances its progress; once it reaches 1.0, actually applies it to `self.cube`."""
        if self._move_in_progress is None:
            return

        self._move_in_progress.progress += dt / self._move_in_progress.duration

        if self._move_in_progress.progress >= 1.0:
            move_name = self._move_in_progress.name
            self.cube.apply_move(move_name)

            if self._move_in_progress.record_in_history:
                self._undo_stack.append(move_name)
                self._redo_stack.clear()

            self._move_in_progress = None
            self._continue_move_queue()

    # --- "Shuffle" button --------------------------------------------------

    def _shuffle(self) -> None:
        """
        Builds a random sequence of `SCRAMBLE_MOVE_COUNT` moves and
        queues it to be animated one after another (see
        `_continue_move_queue`), faster than a manual turn
        (`SCRAMBLE_ANIMATION_DURATION`). Each move is actually applied
        only once it finishes animating -- same as a manual one --, so
        `self.cube` is always a valid, reachable-by-real-turns state.

        Scrambling resets undo/redo history (`_undo_stack`/
        `_redo_stack`): none of its individual moves get recorded (see
        `_continue_move_queue`), so the scramble itself can't be
        undone move by move. The freshly scrambled state becomes the
        new baseline -- undo/redo start working again, normally, only
        for moves made from this point on.
        """
        if self._shuffling or self._move_in_progress is not None:
            return

        self._undo_stack.clear()
        self._redo_stack.clear()

        self._shuffling = True
        self._move_queue = [
            random.choice(ALL_MOVES) for _ in range(SCRAMBLE_MOVE_COUNT)
        ]
        self._continue_move_queue()

    def _activate_auto(self) -> None:
        """
        Handler for the "Auto" button: scrambles the cube exactly like
        "Shuffle" (`_shuffle`), and arms the timer to start the moment
        that scramble actually finishes animating (see
        `_continue_move_queue`) -- not the instant the button is
        pressed. This is the *only* path that touches the timer --
        plain "Shuffle" never does, so scrambling by hand isn't timed.

        Guarded the same way `_shuffle` guards itself (busy shuffling
        or a move mid-animation): if `_shuffle` is going to be a no-op,
        the timer must not be armed either.
        """
        if self._shuffling or self._move_in_progress is not None:
            return

        self._shuffle()
        self._timer_pending_start = True

    def _continue_move_queue(self) -> None:
        """
        Starts the next move queued by `_shuffle`, or -- once none are
        left -- marks the shuffle as finished and, if it was triggered
        by "Auto" (`_timer_pending_start`), starts the timer at 00:00
        right here, now that the scramble is actually done.
        """
        if self._move_queue:
            next_move = self._move_queue.pop(0)
            self._start_move(next_move, duration=SCRAMBLE_ANIMATION_DURATION, record_in_history=False)
            return

        self._shuffling = False

        if self._timer_pending_start:
            self._timer_pending_start = False
            self._timer_started = True
            self._timer_running = True
            self._timer_elapsed = 0.0

    # --- "Undo"/"Redo" buttons -----------------------------------------------

    def _undo(self) -> None:
        """
        Steps back the last move actually applied to the cube: pops it
        off `_undo_stack`, animates its inverse (see `inverse_move`),
        and pushes the original move onto `_redo_stack` so `_redo` can
        bring it back. Does nothing while a move/shuffle is already in
        progress, or once there's nothing left to undo.
        """
        if self._shuffling or self._move_in_progress is not None or not self._undo_stack:
            return

        move_name = self._undo_stack.pop()
        self._redo_stack.append(move_name)
        self._start_move(inverse_move(move_name), record_in_history=False)

    def _redo(self) -> None:
        """
        Re-applies the last move undone by `_undo`: pops it off
        `_redo_stack`, animates it forward again, and pushes it back
        onto `_undo_stack`. Does nothing while a move/shuffle is
        already in progress, or once there's nothing left to redo.
        """
        if self._shuffling or self._move_in_progress is not None or not self._redo_stack:
            return

        move_name = self._redo_stack.pop()
        self._undo_stack.append(move_name)
        self._start_move(move_name, record_in_history=False)

    # --- "Search" button (A03) ----------------------------------------------

    def _search_for_block(self) -> None:
        """
        Runs the A03 challenge (`RubikCube.search_3d_pattern`, see
        `src/algorithm.py::find_3d_pattern`) against the cube's
        current state, looking for `self._target_pattern` -- the
        2x2x2 corner block captured from the solved cube in `enter`.

        If found, highlights the 8 positions of the matching block in
        the 3D view (see `render`'s call to `draw_cube_3d`); if not,
        clears the highlight. Either way, `_search_found` drives a
        quick color cue on the button itself (see
        `_draw_search_button`).
        """
        origin = self.cube.search_3d_pattern(self._target_pattern)

        if origin is None:
            self._search_highlight = None
            self._search_found = False
            return

        origin_x, origin_y, origin_z = origin
        self._search_highlight = frozenset(
            (origin_x + i, origin_y + j, origin_z + k)
            for i in range(SEARCH_BLOCK_SIZE)
            for j in range(SEARCH_BLOCK_SIZE)
            for k in range(SEARCH_BLOCK_SIZE)
        )
        self._search_found = True

    # --- Scramble timer ------------------------------------------------------

    def _advance_timer(self, dt: float) -> None:
        """
        Counts up while `_timer_running`, then freezes the moment the
        cube is solved again. The check is skipped while `_shuffling`
        is True as a safety net against a plain "Shuffle" run while the
        timer is already going -- `self.cube` only reflects a queued
        move once it finishes animating (see `_advance_move_in_progress`),
        so mid-reshuffle it could otherwise misread a not-yet-updated,
        still-solved cube as a solve.
        """
        if not self._timer_running:
            return

        self._timer_elapsed += dt

        if not self._shuffling and self.cube.is_solved():
            self._timer_running = False

    def _render_pixel_text(self, font: pygame.font.Font, text: str, color, scale: int) -> pygame.Surface:
        """Same blocky/pixel-art rendering MenuState/InstructionsState use, kept local so this state doesn't depend on them."""
        small = font.render(text, False, color)
        size = (max(1, small.get_width() * scale), max(1, small.get_height() * scale))
        return pygame.transform.scale(small, size)

    def _rotate_camera_continuously(self, dt: float) -> None:
        """Applies, based on which arrows are currently held, this frame's rotation (see `_camera_keys_held`)."""
        step = KEYBOARD_ROTATION_SPEED * dt

        if self._camera_keys_held[_CAMERA_ACTION_LEFT]:
            self.yaw -= step
        if self._camera_keys_held[_CAMERA_ACTION_RIGHT]:
            self.yaw += step
        if self._camera_keys_held[_CAMERA_ACTION_UP]:
            self.pitch = min(MAX_PITCH, self.pitch + step)
        if self._camera_keys_held[_CAMERA_ACTION_DOWN]:
            self.pitch = max(-MAX_PITCH, self.pitch - step)

    # --- 3D rotation with the mouse ----------------------------------------

    def _virtual_position(self, data: MouseClickData) -> Tuple[float, float]:
        x, y = data.position
        return (
            x * settings.VIRTUAL_WIDTH / settings.WINDOW_WIDTH,
            y * settings.VIRTUAL_HEIGHT / settings.WINDOW_HEIGHT,
        )

    def _rotate_view(self, dx: float, dy: float) -> None:
        self.yaw += dx * DRAG_SENSITIVITY
        self.pitch += dy * DRAG_SENSITIVITY
        self.pitch = max(-MAX_PITCH, min(MAX_PITCH, self.pitch))

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if input_id in _VALID_MOVES and isinstance(input_data, KeyboardData):
            if input_data.pressed:
                self._start_move(input_id)

        elif input_id in _CAMERA_ACTIONS and isinstance(input_data, KeyboardData):
            if input_data.pressed:
                self._camera_keys_held[input_id] = True
            elif input_data.released:
                self._camera_keys_held[input_id] = False

        elif input_id == "mouse_click" and isinstance(input_data, MouseClickData):
            if input_data.pressed:
                position = self._virtual_position(input_data)
                if self._shuffle_button_rect.collidepoint(position):
                    self._shuffle()
                elif self._auto_button_rect.collidepoint(position):
                    self._activate_auto()
                elif self._eye_button_rect.collidepoint(position):
                    self._face_guide_active = not self._face_guide_active
                elif self._search_button_rect.collidepoint(position):
                    self._search_for_block()
                elif self._undo_button_rect.collidepoint(position):
                    self._undo()
                elif self._redo_button_rect.collidepoint(position):
                    self._redo()
                else:
                    self.dragging = True
                    self._last_mouse_pos = position
            elif input_data.released:
                self.dragging = False
                self._last_mouse_pos = None

        elif input_id == "mouse_motion" and isinstance(input_data, MouseMotionData):
            x, y = input_data.position
            vx = x * settings.VIRTUAL_WIDTH / settings.WINDOW_WIDTH
            vy = y * settings.VIRTUAL_HEIGHT / settings.WINDOW_HEIGHT

            if self.dragging and self._last_mouse_pos is not None:
                dx = vx - self._last_mouse_pos[0]
                dy = vy - self._last_mouse_pos[1]
                self._rotate_view(dx, dy)

            self._last_mouse_pos = (vx, vy)

    def update(self, dt: float) -> None:
        self._rotate_camera_continuously(dt)
        self._advance_move_in_progress(dt)
        self._advance_timer(dt)

        if self._shuffling:
            self._shuffle_icon_angle += SHUFFLING_ICON_SPIN_SPEED * dt
            self._shuffle_icon_angle %= 2 * math.pi
        else:
            self._shuffle_icon_angle = 0.0

    def _draw_shuffle_button(self, surface: pygame.Surface) -> None:
        is_hovered = (
            self._last_mouse_pos is not None
            and self._shuffle_button_rect.collidepoint(self._last_mouse_pos)
        )
        background_color = SHUFFLE_BUTTON_HOVER_COLOR if is_hovered else SHUFFLE_BUTTON_COLOR

        pygame.draw.rect(surface, background_color, self._shuffle_button_rect, border_radius=8)
        pygame.draw.rect(
            surface, SHUFFLE_BUTTON_BORDER_COLOR, self._shuffle_button_rect, width=1, border_radius=8
        )

        icon = self._shuffle_icon
        if self._shuffling:
            icon = pygame.transform.rotate(icon, -math.degrees(self._shuffle_icon_angle))
        surface.blit(icon, icon.get_rect(center=self._shuffle_button_rect.center))

    def _draw_auto_button(self, surface: pygame.Surface) -> None:
        is_hovered = (
            self._last_mouse_pos is not None
            and self._auto_button_rect.collidepoint(self._last_mouse_pos)
        )
        if self._timer_running:
            background_color = AUTO_BUTTON_ACTIVE_COLOR
        elif is_hovered:
            background_color = AUTO_BUTTON_HOVER_COLOR
        else:
            background_color = AUTO_BUTTON_COLOR

        pygame.draw.rect(surface, background_color, self._auto_button_rect, border_radius=8)
        pygame.draw.rect(
            surface, AUTO_BUTTON_BORDER_COLOR, self._auto_button_rect, width=1, border_radius=8
        )

        surface.blit(self._auto_icon, self._auto_icon.get_rect(center=self._auto_button_rect.center))

    def _draw_eye_button(self, surface: pygame.Surface) -> None:
        is_hovered = (
            self._last_mouse_pos is not None
            and self._eye_button_rect.collidepoint(self._last_mouse_pos)
        )
        if self._face_guide_active:
            background_color = EYE_BUTTON_ACTIVE_COLOR
        elif is_hovered:
            background_color = EYE_BUTTON_HOVER_COLOR
        else:
            background_color = EYE_BUTTON_COLOR

        pygame.draw.rect(surface, background_color, self._eye_button_rect, border_radius=8)
        pygame.draw.rect(
            surface, EYE_BUTTON_BORDER_COLOR, self._eye_button_rect, width=1, border_radius=8
        )

        icon = self._eye_open_icon if self._face_guide_active else self._eye_closed_icon
        surface.blit(icon, icon.get_rect(center=self._eye_button_rect.center))

    def _draw_search_button(self, surface: pygame.Surface) -> None:
        is_hovered = (
            self._last_mouse_pos is not None
            and self._search_button_rect.collidepoint(self._last_mouse_pos)
        )
        if self._search_found is True:
            background_color = SEARCH_BUTTON_FOUND_COLOR
        elif self._search_found is False:
            background_color = SEARCH_BUTTON_NOT_FOUND_COLOR
        elif is_hovered:
            background_color = SEARCH_BUTTON_HOVER_COLOR
        else:
            background_color = SEARCH_BUTTON_COLOR

        pygame.draw.rect(surface, background_color, self._search_button_rect, border_radius=8)
        pygame.draw.rect(
            surface, SEARCH_BUTTON_BORDER_COLOR, self._search_button_rect, width=1, border_radius=8
        )

        surface.blit(self._search_icon, self._search_icon.get_rect(center=self._search_button_rect.center))

    def _draw_history_button(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        icon: pygame.Surface,
        dimmed_icon: pygame.Surface,
        enabled: bool,
    ) -> None:
        is_hovered = (
            enabled
            and self._last_mouse_pos is not None
            and rect.collidepoint(self._last_mouse_pos)
        )
        background_color = HISTORY_BUTTON_HOVER_COLOR if is_hovered else HISTORY_BUTTON_COLOR

        pygame.draw.rect(surface, background_color, rect, border_radius=8)
        pygame.draw.rect(surface, HISTORY_BUTTON_BORDER_COLOR, rect, width=1, border_radius=8)

        shown_icon = icon if enabled else dimmed_icon
        surface.blit(shown_icon, shown_icon.get_rect(center=rect.center))

    def _draw_timer(self, surface: pygame.Surface) -> None:
        """
        Bottom-right "LCD" panel showing the scramble timer, blocky
        pixel-art digits (see `_render_pixel_text`). Only called once
        `_timer_started` is True (see `render`) -- it stays off-screen
        entirely until "Auto" is pressed for the first time. Text/border
        color double as a state cue: bright green while counting
        (`_timer_running`), white-on-green border once frozen by a solve.
        """
        minutes, seconds = divmod(int(self._timer_elapsed), 60)
        label = f"{minutes:02d}:{seconds:02d}"

        text_color = TIMER_RUNNING_TEXT_COLOR if self._timer_running else TIMER_SOLVED_TEXT_COLOR
        digits = self._render_pixel_text(self._timer_font, label, text_color, TIMER_TEXT_SCALE)

        panel_width = digits.get_width() + TIMER_PANEL_PADDING_X * 2
        panel_height = digits.get_height() + TIMER_PANEL_PADDING_Y * 2
        panel_rect = pygame.Rect(0, 0, panel_width, panel_height)
        panel_rect.right = settings.VIRTUAL_WIDTH - TIMER_RIGHT_MARGIN
        panel_rect.bottom = settings.VIRTUAL_HEIGHT - TIMER_BOTTOM_MARGIN

        border_color = TIMER_BORDER_COLOR if self._timer_running else TIMER_SOLVED_BORDER_COLOR

        pygame.draw.rect(surface, TIMER_BG_COLOR, panel_rect, border_radius=6)
        pygame.draw.rect(surface, border_color, panel_rect, width=1, border_radius=6)
        surface.blit(digits, digits.get_rect(center=panel_rect.center))

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(COLOR_BG)

        animation = None
        if self._move_in_progress is not None:
            animation = LayerAnimation(
                axis=self._move_in_progress.axis,
                indices=self._move_in_progress.indices,
                clockwise=self._move_in_progress.clockwise,
                progress=min(1.0, self._move_in_progress.progress),
            )

        cube_center = (settings.VIRTUAL_WIDTH / 2, settings.VIRTUAL_HEIGHT / 2)

        draw_cube_3d(
            surface,
            self.cube,
            self.yaw,
            self.pitch,
            center=cube_center,
            scale=CUBE_SCALE,
            highlight=self._search_highlight,
            animation=animation,
        )

        if self._face_guide_active:
            draw_face_guide(
                surface, self.yaw, self.pitch, cube_center, CUBE_SCALE, self._guide_font
            )

        self._draw_shuffle_button(surface)
        self._draw_auto_button(surface)
        self._draw_eye_button(surface)
        self._draw_search_button(surface)
        self._draw_history_button(
            surface, self._undo_button_rect, self._undo_icon, self._undo_icon_dimmed,
            enabled=bool(self._undo_stack),
        )
        self._draw_history_button(
            surface, self._redo_button_rect, self._redo_icon, self._redo_icon_dimmed,
            enabled=bool(self._redo_stack),
        )

        if self._timer_started:
            self._draw_timer(surface)
