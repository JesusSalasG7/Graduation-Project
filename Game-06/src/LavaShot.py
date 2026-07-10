
import random

from src.GameObject import GameObject


class LavaShot(GameObject):
    """
    Hazard that waits inside a lava tile, then periodically rises out of it,
    holds briefly, and sinks back down, repeating with a new random wait each
    cycle so spawn points across the level don't rise in sync.
    """

    RISE_HEIGHT = 40
    RISE_SPEED = 60
    FALL_SPEED = 40
    HOLD_TIME = 1.0
    WAIT_MIN = 1.5
    WAIT_MAX = 4.0

    def __init__(self, x: float, lava_y: float) -> None:
        self.lava_y = lava_y
        self.peak_y = lava_y - self.RISE_HEIGHT
        super().__init__(
            x,
            lava_y,
            16,
            16,
            "shot",
            0,
            GameObject.DEFAULT_SOLIDNESS,
        )
        self.state = "hidden"
        self.active = False
        self.timer = random.uniform(self.WAIT_MIN, self.WAIT_MAX)

    def update(self, dt: float) -> None:
        if self.state == "hidden":
            self.timer -= dt
            if self.timer <= 0:
                self.state = "rising"
                self.active = True
        elif self.state == "rising":
            self.y = max(self.peak_y, self.y - self.RISE_SPEED * dt)
            if self.y <= self.peak_y:
                self.state = "holding"
                self.timer = self.HOLD_TIME
        elif self.state == "holding":
            self.timer -= dt
            if self.timer <= 0:
                self.state = "falling"
        elif self.state == "falling":
            self.y = min(self.lava_y, self.y + self.FALL_SPEED * dt)
            if self.y >= self.lava_y:
                self.state = "hidden"
                self.active = False
                self.timer = random.uniform(self.WAIT_MIN, self.WAIT_MAX)
