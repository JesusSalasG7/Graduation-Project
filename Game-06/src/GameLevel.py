
from typing import Any, Dict

import pygame

import settings
from src.Creature import Creature
from src.GameItem import GameItem
from src.GameObject import GameObject
from src.definitions import creatures, items, traps

# Position (in pixels) of the key needed to challenge the boss, roughly at the
# midpoint of level 2, resting on the long platform that crosses the level.
BOSS_KEY_POSITION = (544, 144)


class GameLevel:
    def __init__(self, num_level: int) -> None:
        self.tilemap = None
        self.creatures = []
        self.items = []
        self.traps = []
        self.num_level = num_level
        settings.LevelLoader().load(self, settings.TILEMAPS[num_level])

        if num_level == 2:
            self._add_boss_key()

    def _add_boss_key(self) -> None:
        x, y = BOSS_KEY_POSITION
        self.items.append(
            GameItem(
                collidable=True,
                consumable=True,
                on_consume=items.pickup_key,
                x=x,
                y=y,
                width=16,
                height=16,
                texture_id="key",
                frame_index=0,
                solidness=GameObject.DEFAULT_SOLIDNESS,
            )
        )

    def add_trap(self, trap_data: Dict[str, Any]) -> None:
        trap_name = trap_data.pop("trap_name")
        definition = traps.TRAPS[trap_name][trap_data["frame_index"]]
        definition.update(trap_data)
        self.traps.append(GameItem(**definition))    

    def add_item(self, item_data: Dict[str, Any]) -> None:
        item_name = item_data.pop("item_name")
        definition = items.ITEMS[item_name][item_data["frame_index"]]
        definition.update(item_data)
        self.items.append(GameItem(**definition))

    def add_creature(self, creature_data: Dict[str, Any]) -> None:
        definition = creatures.CREATURES[creature_data["tile_index"]]
        self.creatures.append(
            Creature(
                creature_data["x"],
                creature_data["y"],
                creature_data["width"],
                creature_data["height"],
                self,
                **definition,
            )
        )

    def get_rect(self) -> pygame.Rect:
        return pygame.Rect(0, 0, self.tilemap.width, self.tilemap.height)

    def set_render_boundaries(self, rect: pygame.Rect) -> None:
        self.tilemap.set_render_boundaries(rect)

    def update(self, dt: float) -> None:
        for creature in self.creatures:
            creature.update(dt)

        # Remove dead creatures
        self.creatures = [
            creature for creature in self.creatures if not creature.is_dead
        ]

    def render(self, surface: pygame.Surface) -> None:
        self.tilemap.render(surface)
        for creature in self.creatures:
            creature.render(surface)
        for item in self.items:
            if item.active:
                item.render(surface)
        for trap in self.traps:
            if trap.active:
                trap.render(surface)        
