"""
Title/presentation screen: a colorful pixel-art "RUBIK CUBE" logo over
a slowly spinning cube, with two buttons -- "Start" (jumps straight
into `PlayState`) and "Instructions" (explains every control and
button currently in the game, see `InstructionsState`).
"""
import math
from typing import Any, Dict, List, Optional, Tuple

import pygame

from gale.conf import settings
from gale.input_handler import InputData, MouseClickData, MouseMotionData
from gale.state import BaseState

from src.rubik_cube import BLUE, GREEN, ORANGE, RED, RubikCube, WHITE, YELLOW
from src.view_3d import draw_cube_3d

COLOR_BG = pygame.Color(24, 26, 33)

# --- Decorative cube, spinning on its own (not player-controlled) ------
CUBE_SCALE = 16.0
CUBE_YAW_SPEED = math.radians(20)
CUBE_PITCH = math.radians(32)
CUBE_CENTER = (settings.VIRTUAL_WIDTH / 2, 122.0)

# --- Title, rendered small then upscaled with nearest-neighbor scaling
# (see `_pixel_text_rainbow`) for a blocky, pixel-art look; each
# letter cycles through the cube's own sticker colors for a colorful,
# on-theme banner.
TITLE_TEXT = "RUBIK CUBE"
TITLE_SCALE = 3
TITLE_TOP = 14
TITLE_COLORS: Tuple[Tuple[int, int, int], ...] = (WHITE, YELLOW, RED, ORANGE, BLUE, GREEN)

# --- "Start"/"Instructions" buttons -------------------------------------
BUTTON_WIDTH = 176
BUTTON_HEIGHT = 22
BUTTON_GAP = 10
BUTTON_BOTTOM_MARGIN = 16
BUTTON_TEXT_SCALE = 2

BUTTON_COLOR = pygame.Color(255, 255, 255)
BUTTON_HOVER_COLOR = pygame.Color(210, 225, 250)
BUTTON_BORDER_COLOR = pygame.Color(170, 170, 178)
BUTTON_TEXT_COLOR = (18, 18, 22)


def _pixel_text(font: pygame.font.Font, text: str, color, scale: int) -> pygame.Surface:
    """Renders `text` without antialiasing (hard-edged pixels) and upscales it with nearest-neighbor scaling, for a blocky pixel-art look."""
    small = font.render(text, False, color)
    size = (max(1, small.get_width() * scale), max(1, small.get_height() * scale))
    return pygame.transform.scale(small, size)


def _pixel_text_rainbow(
    font: pygame.font.Font, text: str, colors: Tuple[Tuple[int, int, int], ...], scale: int
) -> pygame.Surface:
    """Same as `_pixel_text`, but cycles `colors` letter by letter (spaces just advance the cursor) instead of using a single color."""
    pieces: List[Tuple[Optional[pygame.Surface], int]] = []
    color_index = 0
    total_width = 0
    max_height = 0

    for char in text:
        if char == " ":
            space_width = font.size(" ")[0]
            pieces.append((None, space_width))
            total_width += space_width
            continue

        color = colors[color_index % len(colors)]
        color_index += 1
        char_surface = font.render(char, False, color)
        pieces.append((char_surface, char_surface.get_width()))
        total_width += char_surface.get_width()
        max_height = max(max_height, char_surface.get_height())

    composed = pygame.Surface((max(1, total_width), max(1, max_height)), pygame.SRCALPHA)
    x = 0
    for char_surface, width in pieces:
        if char_surface is not None:
            composed.blit(char_surface, (x, 0))
        x += width

    size = (composed.get_width() * scale, composed.get_height() * scale)
    return pygame.transform.scale(composed, size)


class MenuState(BaseState):
    def enter(self, *args: Tuple[Any], **kwargs: Dict[str, Any]) -> None:
        self._cube = RubikCube()
        self._yaw = math.radians(-42)

        self._last_mouse_pos: Optional[Tuple[float, float]] = None

        pixel_title_font = settings.FONTS["pixel_title"]
        pixel_button_font = settings.FONTS["pixel_button"]

        self._title_surface = _pixel_text_rainbow(
            pixel_title_font, TITLE_TEXT, TITLE_COLORS, TITLE_SCALE
        )
        self._title_rect = self._title_surface.get_rect(
            centerx=settings.VIRTUAL_WIDTH / 2, top=TITLE_TOP
        )

        self._start_label = _pixel_text(pixel_button_font, "COMENZAR", BUTTON_TEXT_COLOR, BUTTON_TEXT_SCALE)
        self._instructions_label = _pixel_text(
            pixel_button_font, "INSTRUCCIONES", BUTTON_TEXT_COLOR, BUTTON_TEXT_SCALE
        )

        button_left = (settings.VIRTUAL_WIDTH - BUTTON_WIDTH) / 2
        instructions_top = settings.VIRTUAL_HEIGHT - BUTTON_BOTTOM_MARGIN - BUTTON_HEIGHT
        start_top = instructions_top - BUTTON_GAP - BUTTON_HEIGHT

        self._start_button_rect = pygame.Rect(button_left, start_top, BUTTON_WIDTH, BUTTON_HEIGHT)
        self._instructions_button_rect = pygame.Rect(
            button_left, instructions_top, BUTTON_WIDTH, BUTTON_HEIGHT
        )

    def exit(self) -> None:
        pass

    def _virtual_position(self, data: MouseClickData) -> Tuple[float, float]:
        x, y = data.position
        return (
            x * settings.VIRTUAL_WIDTH / settings.WINDOW_WIDTH,
            y * settings.VIRTUAL_HEIGHT / settings.WINDOW_HEIGHT,
        )

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if input_id == "mouse_click" and isinstance(input_data, MouseClickData):
            if input_data.pressed:
                position = self._virtual_position(input_data)
                if self._start_button_rect.collidepoint(position):
                    self.state_machine.change("play")
                elif self._instructions_button_rect.collidepoint(position):
                    self.state_machine.change("instructions")

        elif input_id == "mouse_motion" and isinstance(input_data, MouseMotionData):
            x, y = input_data.position
            self._last_mouse_pos = (
                x * settings.VIRTUAL_WIDTH / settings.WINDOW_WIDTH,
                y * settings.VIRTUAL_HEIGHT / settings.WINDOW_HEIGHT,
            )

    def update(self, dt: float) -> None:
        self._yaw += CUBE_YAW_SPEED * dt

    def _draw_button(self, surface: pygame.Surface, rect: pygame.Rect, label: pygame.Surface) -> None:
        is_hovered = self._last_mouse_pos is not None and rect.collidepoint(self._last_mouse_pos)
        background_color = BUTTON_HOVER_COLOR if is_hovered else BUTTON_COLOR

        pygame.draw.rect(surface, background_color, rect, border_radius=6)
        pygame.draw.rect(surface, BUTTON_BORDER_COLOR, rect, width=1, border_radius=6)
        surface.blit(label, label.get_rect(center=rect.center))

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(COLOR_BG)

        draw_cube_3d(
            surface,
            self._cube,
            self._yaw,
            CUBE_PITCH,
            center=CUBE_CENTER,
            scale=CUBE_SCALE,
        )

        surface.blit(self._title_surface, self._title_rect)

        self._draw_button(surface, self._start_button_rect, self._start_label)
        self._draw_button(surface, self._instructions_button_rect, self._instructions_label)
