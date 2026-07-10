
from typing import TypeVar

from gale.state import BaseState, StateMachine


class BaseEntityState(BaseState):
    def __init__(self, entity: TypeVar("GameEntity"), state_machine: StateMachine) -> None:
        super().__init__(state_machine)
        self.entity = entity

    def bounce_off_world_and_walls(self) -> bool:
        """
        Clamp the entity to the level's horizontal bounds and check for a
        tilemap wall collision on either side. Shared by every patrolling
        entity (creatures, boss) that reverses direction when it hits an
        edge. Returns True if either happened.
        """
        world_width = self.entity.tilemap.width

        if self.entity.x + self.entity.width >= world_width:
            self.entity.x = world_width - self.entity.width
            return True
        elif self.entity.x <= 0:
            self.entity.x = 0
            return True

        return (
            self.entity.handle_tilemap_collision_on_left()
            or self.entity.handle_tilemap_collision_on_right()
        )
