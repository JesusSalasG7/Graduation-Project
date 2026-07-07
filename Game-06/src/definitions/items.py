
from typing import Dict, Any

import random

from gale.timer import Timer

import settings
from src.GameItem import GameItem
from src.Player import Player


def pickup_key( player: Player) -> None:
    settings.SOUNDS["pickup_coin"].stop()
    settings.SOUNDS["pickup_coin"].play()
    # Touching the key no longer grants it outright: it opens the
    # "Where's the Key" puzzle, and solving that is what actually flips
    # player.pickup_key (see PlayState.update / PuzzleState).
    player.key_puzzle_pending = True

def open_door( player: Player) -> None:
    settings.SOUNDS["pickup_coin"].stop()
    settings.SOUNDS["pickup_coin"].play()
    player.open_door = True    

def key( player: Player):
    pickup_key(player)

def door( player: Player):
    open_door(player)

def puzzle( player: Player):
    pass   

ITEMS: Dict[str, Dict[int, Dict[str, Any]]] = {
    "coins": {

        29: {
            "texture_id": "tiles",
            "solidness": dict(top=False, right=False, bottom=False, left=False),
            "consumable": True,
            "collidable": True,
            "on_consume": puzzle,
        },
        74: {
            "texture_id": "tiles2",
            "solidness": dict(top=False, right=False, bottom=False, left=False),
            "consumable": True,
            "collidable": True,
            "on_collide": door,
        },
        82: {
            "texture_id": "tiles2",
            "solidness": dict(top=False, right=False, bottom=False, left=False),
            "consumable": True,
            "collidable": True,
            "on_collide": door,
        },
        90: {
            "texture_id": "tiles2",
            "solidness": dict(top=False, right=False, bottom=False, left=False),
            "consumable": True,
            "collidable": True,
            "on_consume": key,
        },
    },
}
