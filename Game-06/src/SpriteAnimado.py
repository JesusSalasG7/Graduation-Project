from typing import TypeVar, Dict, Any, Tuple

from gale.state import StateMachine, BaseState

from src import mixins
from src.GameObject import GameObject
from src.GameItem import GameItem

class SpriteAnimado(mixins.DrawableMixin, mixins.AnimatedMixin):
    def __init__( self,
            x: float,
            y: float,
            width: float,
            height: float,
            texture_id: str,
            animation_defs: Dict[str, Dict[str, Any]],
        ) -> None:
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.animations = {}
        self.current_animation = None
        self.frame_index = 0
        self.current_animation = None
        self.texture_id = texture_id
        self.frame_index = -1
        self.generate_animations(animation_defs)
        self.flipped = False

    def update(self, dt):
        mixins.AnimatedMixin.update(self, dt)



