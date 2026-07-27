"""
The state that runs the actual game: wires player input to the World
(the model) and delegates drawing to the WorldRenderer (the view).
"""
from typing import Any, Dict, Tuple

import pygame

from gale.input_handler import InputData
from gale.state import BaseState

import settings
from src.audio.ambient import AmbientController
from src.direction import Direction
from src.rendering.world_renderer import WorldRenderer
from src.world import World

_DIRECTION_BY_ACTION = {
    "move_up": Direction.UP,
    "move_down": Direction.DOWN,
    "move_left": Direction.LEFT,
    "move_right": Direction.RIGHT,
}


class PlayState(BaseState):
    def enter(self, *args: Tuple[Any], mode: str = "classic", **kwargs: Dict[str, Any]) -> None:
        self.world = World(
            settings.GRID_COLS, settings.GRID_ROWS, settings.MOVE_INTERVAL, mode=mode
        )
        self.renderer = WorldRenderer(self.world)
        self.ambient = AmbientController()
        self.ambient.start()
        self._start_theme_music()

    def _start_theme_music(self) -> None:
        pygame.mixer.music.load(str(settings.THEME_MUSIC_PATH))
        pygame.mixer.music.set_volume(settings.THEME_MUSIC_VOLUME)
        pygame.mixer.music.play(loops=-1)

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if not input_data.pressed:
            return

        direction = _DIRECTION_BY_ACTION.get(input_id)

        if direction is not None:
            if not self.world.finished:
                settings.SOUNDS["move"].play()

            self.world.set_direction(direction)
        elif input_id == "restart" and self.world.finished:
            self.world.reset()
            self._start_theme_music()

    def update(self, dt: float) -> None:
        self.world.update(dt)

        if self.world.consume_impact_event():
            settings.SOUNDS["crash"].play()
            self.ambient.duck()
            pygame.mixer.music.stop()

        if self.world.consume_eat_event():
            settings.SOUNDS["eat"].play()
            self.ambient.duck()

        self.ambient.sync_with_world(self.world)
        self.ambient.update(dt)

    def render(self, surface: pygame.Surface) -> None:
        self.renderer.render(surface)
