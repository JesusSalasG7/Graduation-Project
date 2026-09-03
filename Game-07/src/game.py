"""
ConwayGame: the gale.game.Game subclass wiring everything together.

Combines a gale.state.StateMachine (start <-> play) with a
gale.state.StateStack used purely as an overlay layer: whenever it
holds a state (currently only VictoryState), that overlay renders on
top of -- and exclusively receives input over -- whatever the state
machine is currently showing, which is how the "victory popup drawn
over the still-visible grid" behavior is achieved with Gale's own
primitives instead of a bespoke mechanism.
"""
import pygame

from gale.game import Game
from gale.input_handler import InputData
from gale.state import StateMachine, StateStack

import settings
from src.achievements import AchievementsManager
from src.states.play_state import PlayState
from src.states.start_state import StartState
from src.states.victory_state import VictoryState


class ConwayGame(Game):
    def init(self) -> None:
        self.achievements = AchievementsManager()
        self.overlay_stack = StateStack()
        self.state_machine = StateMachine(
            {
                "start": lambda sm: StartState(sm, self),
                "play": lambda sm: PlayState(sm, self),
            }
        )
        self.state_machine.change("start")

    def show_victory(self, level_index: int, **stats) -> None:
        self.overlay_stack.push(VictoryState(self), level_index=level_index, **stats)

    def hide_overlay(self) -> None:
        self.overlay_stack.pop()

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if input_id == "confirm" and input_data.pressed:
            settings.SOUNDS["click"].play()

        if self.overlay_stack.states:
            self.overlay_stack.on_input(input_id, input_data)
        else:
            self.state_machine.on_input(input_id, input_data)

    def update(self, dt: float) -> None:
        self.state_machine.update(dt)
        if self.overlay_stack.states:
            self.overlay_stack.update(dt)

    def render(self, surface: pygame.Surface) -> None:
        self.state_machine.render(surface)
        if self.overlay_stack.states:
            self.overlay_stack.render(surface)
