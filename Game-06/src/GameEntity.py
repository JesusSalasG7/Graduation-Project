"""
ISPPJ1 2024
Study Case: Super Martian (Platformer)

Author: Alejandro Mujica
alejandro.j.mujic4@gmail.com

This file contains the base class GameEntity.
"""

from typing import TypeVar, Dict, Any, Tuple

from gale.state import StateMachine, BaseState

from src import mixins
from src.GameObject import GameObject

class GameEntity(mixins.DrawableMixin, mixins.AnimatedMixin, mixins.CollidableMixin):
    def __init__(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        texture_id: str,
        game_level: TypeVar("GameLevel"),
        states: Dict[str, BaseState],
        animation_defs: Dict[str, Dict[str, Any]],
    ) -> None:
        self.x = x
        self.y = y
        self.prev_x = x
        self.prev_y = y
        self.width = width
        self.height = height
        self.vx: float = 0
        self.vy: float = 0
        self.texture_id = texture_id
        self.frame_index = -1
        self.game_level = game_level
        self.tilemap = self.game_level.tilemap
        self.items = self.game_level.items
        self.state_machine = StateMachine(states)
        self.current_animation = None
        self.animations = {}
        self.generate_animations(animation_defs)
        self.flipped = False
        self.is_dead = False

    def change_state(self, state_id: str, *args: Tuple[Any], **kwargs: Dict[str, Any]) -> None:
        self.state_machine.change(state_id, *args, **kwargs)

    def update(self, dt: float) -> None:
        # Remember where we were before moving so collision checks can sweep
        # every tile row/column crossed this frame instead of just the one
        # next to the destination. Without this, a fast fall (e.g. after
        # dropping from a high place) can move more than one tile in a
        # single frame and tunnel through a platform that was never checked.
        self.prev_x = self.x
        self.prev_y = self.y

        next_x = self.x + self.vx * dt

        if self.vx < 0:
            self.x = max(0, next_x)
        else:
            self.x = min(self.tilemap.width - self.width, next_x)

        self.y += self.vy * dt

        # Move first, then let the state machine resolve collisions against
        # the position we actually ended up in this frame. Resolving them
        # before applying movement (the previous behavior) checked stale,
        # one-frame-old positions and let entities pass through platforms.
        self.state_machine.update(dt)
        mixins.AnimatedMixin.update(self, dt)

    def handle_tilemap_collision_on_top(self) -> bool:
        collision_rect = self.get_collision_rect()

        # Left and right columns
        left = self.tilemap.to_j(collision_rect.left)
        right = self.tilemap.to_j(collision_rect.right)

        # Sweep every row the top edge crossed this frame (moving upward) so
        # a fast upward move can't skip over the row check entirely. This
        # must track the top edge, not the center: with a height taller than
        # one tile, the center can lag a whole row behind the edge that
        # actually reaches the ceiling first.
        prev_i = int(self.tilemap.to_i(self.prev_y))
        i = self.tilemap.to_i(collision_rect.top)

        for row in range(prev_i, i - 1, -1):
            if self.tilemap.collides_tile_on(
                row - 1, left, self, GameObject.BOTTOM
            ) or self.tilemap.collides_tile_on(row - 1, right, self, GameObject.BOTTOM):
                # Fix the entity position
                self.y = self.tilemap.to_y(row)
                return True

        return False

    def handle_tilemap_collision_on_bottom(self) -> bool:
        collision_rect = self.get_collision_rect()

        # Left and right columns
        left = self.tilemap.to_j(collision_rect.left)
        right = self.tilemap.to_j(collision_rect.right)

        # Sweep every row the bottom edge crossed this frame (moving
        # downward) so a fast fall (e.g. after dropping from a high place,
        # where gravity has built up enough vy to move more than one tile
        # per frame) can't skip past the platform's row without ever being
        # checked. This must track the bottom edge, not the center: with a
        # height taller than one tile, the center can lag a whole row behind
        # the edge that actually reaches the floor first.
        prev_i = int(self.tilemap.to_i(self.prev_y + self.height - 1))
        i = self.tilemap.to_i(collision_rect.bottom - 1)

        for row in range(prev_i, i + 1):
            if self.tilemap.collides_tile_on(
                row + 1, left, self, GameObject.TOP
            ) or self.tilemap.collides_tile_on(row + 1, right, self, GameObject.TOP):
                # Fix the entity position
                self.y = self.tilemap.to_y(row + 1) - self.height
                return True

        return False

    def handle_tilemap_collision_on_right(self) -> bool:
        collision_rect = self.get_collision_rect()

        # Top and bottom rows. The entity's height is taller than one tile
        # (e.g. 17px on a 16px grid), so its box always spans exactly two
        # tile rows. Using the center row here used to skip the bottom one
        # almost every frame (center rounds down to the top row far more
        # often than not), letting the bottom-corner of the box clip through
        # a ledge/overhang while airborne (e.g. jumping sideways into the
        # underside of a platform) without ever being detected.
        top = self.tilemap.to_i(collision_rect.top)
        bottom = self.tilemap.to_i(collision_rect.bottom - 1)

        # Sweep every column the center crossed this frame (moving right).
        prev_j = int(self.tilemap.to_j(self.prev_x + self.width / 2))
        j = self.tilemap.to_j(collision_rect.centerx)

        for col in range(prev_j, j + 1):
            if self.tilemap.collides_tile_on(
                top, col + 1, self, GameObject.LEFT
            ) or self.tilemap.collides_tile_on(bottom, col + 1, self, GameObject.LEFT):
                # Fix the entity position
                self.x = self.tilemap.to_x(col + 1) - self.width
                return True

        return False

    def handle_tilemap_collision_on_left(self) -> bool:
        collision_rect = self.get_collision_rect()

        # See handle_tilemap_collision_on_right for why bottom (not center).
        top = self.tilemap.to_i(collision_rect.top)
        bottom = self.tilemap.to_i(collision_rect.bottom - 1)

        # Sweep every column the center crossed this frame (moving left).
        prev_j = int(self.tilemap.to_j(self.prev_x + self.width / 2))
        j = self.tilemap.to_j(collision_rect.centerx)

        for col in range(prev_j, j - 1, -1):
            if self.tilemap.collides_tile_on(
                top, col - 1, self, GameObject.RIGHT
            ) or self.tilemap.collides_tile_on(bottom, col - 1, self, GameObject.RIGHT):
                # Fix the entity position
                self.x = self.tilemap.to_x(col)
                return True

        return False

    def check_floor(self) -> bool:
     
        collision_rect = self.get_collision_rect()

        # Row for the center of the player
        i = self.tilemap.to_i(collision_rect.centery)
        # Left and right columns
        left = self.tilemap.to_j(collision_rect.left)
        right = self.tilemap.to_j(collision_rect.right)
        return self.tilemap.check_solidness_on(
            i + 1, left, GameObject.TOP
        ) or self.tilemap.check_solidness_on(i + 1, right, GameObject.TOP)

