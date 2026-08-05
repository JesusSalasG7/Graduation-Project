"""
The state that runs the actual game: wires player input to the World
(the model) and delegates drawing to the WorldRenderer (the view).
"""
from typing import Any, Dict, Tuple

import pygame

from gale.input_handler import InputData
from gale.state import BaseState
from src.rendering.pixel_text import render_text

import settings
from src import records
from src.audio.ambient import AmbientController
from src.direction import Direction
from src.rendering.controls_modal import ControlsModal
from src.rendering.world_renderer import WorldRenderer
from src.world import World

_DIRECTION_BY_ACTION = {
    "move_up": Direction.UP,
    "move_down": Direction.DOWN,
    "move_left": Direction.LEFT,
    "move_right": Direction.RIGHT,
}

_MAX_RECORD_NAME_LENGTH = 12

# Shown when the typed name already has an entry on the leaderboard --
# navigated/confirmed the same way as _GAME_OVER_OPTIONS. "rename" is
# listed second and is the default selection (see enter()) so mashing
# ENTER never silently overwrites a previous run by accident.
_OVERWRITE_OPTIONS = ("overwrite", "rename")
_OVERWRITE_LABELS = ("Sobrescribir", "Cambiar nombre")

# Shown as the two selectable "buttons" once a match ends -- navigated
# with move_up/move_down and confirmed with "restart" (ENTER), same
# input vocabulary MenuState uses to pick a mode.
_GAME_OVER_OPTIONS = ("restart", "menu")


class PlayState(BaseState):
    def enter(self, *args: Tuple[Any], mode: str = "classic", **kwargs: Dict[str, Any]) -> None:
        self.world = World(
            settings.GRID_COLS, settings.GRID_ROWS, settings.MOVE_INTERVAL, mode=mode
        )
        self.renderer = WorldRenderer(self.world)
        self.ambient = AmbientController()
        self.ambient.start()
        self._start_theme_music()

        # Set the instant a run ends above the saved best (see update()),
        # so the player can attach their name to it before restarting --
        # entirely PlayState-side UI flow, not part of World's model.
        self._entering_record_name = False
        self._record_name = ""

        # Set instead of committing the record the instant the typed name
        # turns out to already be on the leaderboard, so the player can
        # choose to overwrite that entry or go back and pick another name
        # -- see _handle_record_name_input/_handle_overwrite_confirm_input.
        self._confirming_overwrite = False
        self._overwrite_selected = 1
        self._pending_record_name = ""

        # Which game-over button is highlighted; reset every match so a
        # new round never inherits the previous one's selection.
        self._game_over_selected = 0

        # Shown once per match, right as the chosen mode starts (not back
        # in the menu), so the player sees how to move before the snake
        # actually starts responding -- dismissed with "restart" (ENTER),
        # same as everywhere else in the UI.
        self._showing_controls = True
        self._controls_modal = ControlsModal(
            settings.VIRTUAL_WIDTH // 2, settings.VIRTUAL_HEIGHT // 2
        )

    def exit(self) -> None:
        # Only reachable via the "menu" game-over button today -- without
        # this the ambient drone (looped on fixed mixer channels) would
        # keep playing under the menu forever.
        self.ambient.stop()
        pygame.mixer.music.stop()

    def _start_theme_music(self) -> None:
        pygame.mixer.music.load(str(settings.THEME_MUSIC_PATH))
        pygame.mixer.music.set_volume(settings.THEME_MUSIC_VOLUME)
        pygame.mixer.music.play(loops=-1)

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if not input_data.pressed:
            return

        if self._showing_controls:
            if input_id == "restart":
                self._showing_controls = False
            return

        if self._confirming_overwrite:
            self._handle_overwrite_confirm_input(input_id)
            return

        if self._entering_record_name:
            self._handle_record_name_input(input_id, input_data)
            return

        if self.world.finished:
            self._handle_game_over_input(input_id)
            return

        direction = _DIRECTION_BY_ACTION.get(input_id)

        if direction is not None:
            settings.SOUNDS["move"].play()
            self.world.set_direction(direction)

    def _handle_game_over_input(self, input_id: str) -> None:
        if input_id in ("move_up", "move_down"):
            self._game_over_selected = 1 - self._game_over_selected
        elif input_id == "restart":
            if _GAME_OVER_OPTIONS[self._game_over_selected] == "restart":
                self.world.reset()
                self._game_over_selected = 0
                self._start_theme_music()
            else:
                self.state_machine.change("menu")

    def _handle_record_name_input(self, input_id: str, input_data: InputData) -> None:
        if input_id == "text_backspace":
            self._record_name = self._record_name[:-1]
        elif input_id == "text_char" and len(self._record_name) < _MAX_RECORD_NAME_LENGTH:
            # Names are shown/stored upper-case regardless of the shift
            # state the player actually typed with.
            self._record_name += input_data.unicode.upper()
        elif input_id == "restart":
            name = self._record_name.strip() or "JUGADOR"

            if records.name_exists(name):
                self._pending_record_name = name
                self._overwrite_selected = 1
                self._confirming_overwrite = True
            else:
                records.add(name, self.world.score)
                self._entering_record_name = False

    def _handle_overwrite_confirm_input(self, input_id: str) -> None:
        if input_id in ("move_up", "move_down"):
            self._overwrite_selected = 1 - self._overwrite_selected
        elif input_id == "restart":
            if _OVERWRITE_OPTIONS[self._overwrite_selected] == "overwrite":
                records.overwrite(self._pending_record_name, self.world.score)
                self._entering_record_name = False
            else:
                # "rename": back to the name prompt with a clean slate so
                # the player doesn't just resubmit the same duplicate.
                self._record_name = ""

            self._confirming_overwrite = False

    def update(self, dt: float) -> None:
        if self._showing_controls:
            self._controls_modal.update(dt)
            return

        self.world.update(dt)

        if self.world.consume_impact_event():
            settings.SOUNDS["crash"].play()
            self.ambient.duck()
            pygame.mixer.music.stop()

            if records.qualifies(self.world.score):
                self._entering_record_name = True
                self._record_name = ""

        if self.world.consume_eat_event():
            settings.SOUNDS["eat"].play()
            self.ambient.duck()

        range_bonus = self.world.consume_range_bonus_event()

        if range_bonus is not None and range_bonus[1] > 0:
            settings.SOUNDS["eat"].play()
            self.ambient.duck()

        self.ambient.sync_with_world(self.world)
        self.ambient.update(dt)

    def render(self, surface: pygame.Surface) -> None:
        if self._showing_controls:
            # Just the map and the modal -- the snake/food/HUD only show
            # up once the player has dismissed the tutorial and the
            # actual match begins.
            surface.blit(settings.SPRITES["map"], (0, 0))
            self._controls_modal.render(surface)
            return

        self.renderer.render(
            surface,
            awaiting_record_name=self._entering_record_name,
            game_over_selected=self._game_over_selected,
        )

        if self._entering_record_name:
            self._render_record_name_prompt(surface)

    def _render_record_name_prompt(self, surface: pygame.Surface) -> None:
        center_x = settings.VIRTUAL_WIDTH // 2
        center_y = settings.VIRTUAL_HEIGHT // 2 + 48

        if self._confirming_overwrite:
            self._render_overwrite_confirm(surface, center_x, center_y)
            return

        render_text(
            surface,
            "Entraste a los records! Escribe tu nombre:",
            settings.FONTS["hud"],
            center_x,
            center_y,
            settings.UI_ACCENT_COLOR,
            center=True,
            shadowed=True,
        )
        render_text(
            surface,
            self._record_name + "_",
            settings.FONTS["hud"],
            center_x,
            center_y + 18,
            settings.UI_TEXT_COLOR,
            center=True,
            shadowed=True,
        )

    def _render_overwrite_confirm(self, surface: pygame.Surface, center_x: int, center_y: int) -> None:
        render_text(
            surface,
            f"Ya existe el nombre '{self._pending_record_name}' en los records",
            settings.FONTS["hud"],
            center_x,
            center_y,
            settings.UI_ACCENT_COLOR,
            center=True,
            shadowed=True,
        )

        for i, label in enumerate(_OVERWRITE_LABELS):
            selected = i == self._overwrite_selected
            color = settings.UI_ACCENT_COLOR if selected else settings.UI_TEXT_COLOR
            prefix = "> " if selected else "  "
            render_text(
                surface,
                prefix + label,
                settings.FONTS["menu"],
                center_x,
                center_y + 20 + i * 20,
                color,
                center=True,
                shadowed=True,
            )
