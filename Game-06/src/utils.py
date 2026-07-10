from typing import Tuple

import pygame


def fit_texture_to_area(
    texture: pygame.Surface, area_width: int, area_height: int
) -> Tuple[pygame.Surface, int, int]:
    """
    Scale texture to fit inside (area_width, area_height) preserving its
    aspect ratio (letterboxed, never cropped). Returns the scaled surface
    along with the (x, y) offset to blit it centered in the area.
    """
    original_width, original_height = texture.get_size()
    scale = min(area_width / original_width, area_height / original_height)

    scaled_width = int(original_width * scale)
    scaled_height = int(original_height * scale)
    scaled_texture = pygame.transform.smoothscale(texture, (scaled_width, scaled_height))

    x = (area_width - scaled_width) // 2
    y = (area_height - scaled_height) // 2
    return scaled_texture, x, y
