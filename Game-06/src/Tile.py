from typing import Dict

from typing import Dict

from src.GameObject import GameObject


class Tile(GameObject):
    def __init__(
        self,
        i: int,
        j: int,
        width: int,
        height: int,
        frame_index: int,
        id_textures: str,
        soliness: Dict[str, bool],
    ) -> None:
        self.i = i
        self.j = j
        super().__init__(
            self.j * width,
            self.i * height,
            width,
            height,
            id_textures,
            frame_index,
            soliness,
        )