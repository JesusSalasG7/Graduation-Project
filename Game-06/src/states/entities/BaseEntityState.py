
from typing import TypeVar

from gale.state import BaseState, StateMachine


class BaseEntityState(BaseState):
    def __init__(self, entity: TypeVar("GameEntity"), state_machine: StateMachine) -> None:
        super().__init__(state_machine)
        self.entity = entity
