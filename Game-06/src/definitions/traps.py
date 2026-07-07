
from typing import Dict, Any

import random

from gale.timer import Timer

import settings
from src.GameItem import GameItem
from src.Player import Player



TRAPS: Dict[str, Dict[int, Dict[str, Any]]] = {
    "traps": {
         38: {
            "texture_id": "tiles3",
            "solidness":  dict(top=True, right=True, bottom=True, left=True),
            "consumable": False,
            "collidable": True,
            "on_consume": None,
        },
        49: {
            "texture_id": "tiles3",
            "solidness":  dict(top=True, right=True, bottom=True, left=True),
            "consumable": False,
            "collidable": True,
            "on_consume": None,
        },
         51: {
            "texture_id": "tiles3",
            "solidness":  dict(top=True, right=True, bottom=True, left=True),
            "consumable": False,
            "collidable": True,
            "on_consume": None,
        },
         59: {
            "texture_id": "tiles3",
            "solidness":  dict(top=True, right=True, bottom=True, left=True),
            "consumable": False,
            "collidable": True,
            "on_consume": None,
        },

    },
}
