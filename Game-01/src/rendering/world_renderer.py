"""
Draws a World onto a pygame surface. All rendering concerns (which
sprite goes where, HUD text, the game-over overlay) live here so the
model in src/world.py never has to know pygame exists.
"""
import math
from typing import Tuple

import pygame

from gale.text import render_text

import settings
from src.world import World

Cell = Tuple[int, int]


class WorldRenderer:
    def __init__(self, world: World) -> None:
        self.world = world

    def render(
        self,
        surface: pygame.Surface,
        awaiting_record_name: bool = False,
        game_over_selected: int = 0,
    ) -> None:
        surface.blit(settings.SPRITES["map"], (0, 0))
        self._render_food(surface)
        self._render_snake(surface)
        self._render_impact_stars(surface)
        self._render_hud(surface)

        if self.world.game_over:
            self._render_game_over(surface, awaiting_record_name, game_over_selected)

    @staticmethod
    def _cell_topleft(cell: Cell) -> Tuple[int, int]:
        x, y = cell
        return x * settings.CELL_SIZE, y * settings.CELL_SIZE

    @staticmethod
    def _cell_center(cell: Cell) -> Tuple[int, int]:
        x, y = WorldRenderer._cell_topleft(cell)
        half = settings.CELL_SIZE // 2
        return x + half, y + half

    def _render_snake(self, surface: pygame.Surface) -> None:
        segments = self.world.snake.segments
        colors = settings.SNAKE_COLORS
        # Slightly larger than half a cell so consecutive segments
        # overlap and no gap shows at the joints.
        body_radius = settings.CELL_SIZE // 2 + 2

        # Tail to head so the head (drawn separately below) ends up on
        # top of the segment right behind it. i is also each segment's
        # distance from the head (segments[0]), which _bounce_offset
        # uses to fade the recoil out toward the tail.
        for i in range(len(segments) - 1, 0, -1):
            cx, cy = self._cell_center(segments[i])
            offset = self._bounce_offset(i)
            center = (cx + offset[0], cy + offset[1])
            shade = colors["body_light"] if i % 2 == 0 else colors["body_dark"]
            pygame.draw.circle(surface, colors["outline"], center, body_radius + 2)
            pygame.draw.circle(surface, shade, center, body_radius)

        self._render_head(surface, segments[0], self._bounce_offset(0))

    def _bounce_offset(self, segment_index: int) -> Tuple[float, float]:
        """
        Right after impact the head recoils away from the hit and eases
        back into place -- a one-shot bounce driven by world.impact_time,
        not a loop. Segments further from the head (higher index) join
        in less, so only the front of the snake visibly flinches instead
        of the whole body sliding as one rigid block.
        """
        if not self.world.game_over or self.world.impact_cell is None:
            return (0.0, 0.0)

        falloff = 1 - segment_index / settings.BOUNCE_AFFECTED_SEGMENTS

        if falloff <= 0:
            return (0.0, 0.0)

        t = self.world.impact_time

        if t >= settings.BOUNCE_DURATION:
            return (0.0, 0.0)

        direction = self.world.snake.direction
        magnitude = (
            settings.BOUNCE_DISTANCE * falloff * math.sin((t / settings.BOUNCE_DURATION) * math.pi)
        )
        return (-direction.dx * magnitude, -direction.dy * magnitude)

    def _render_head(
        self, surface: pygame.Surface, head_cell: Cell, offset: Tuple[float, float] = (0.0, 0.0)
    ) -> None:
        colors = settings.SNAKE_COLORS
        direction = self.world.snake.direction
        forward = (direction.dx, direction.dy)
        perp = (-direction.dy, direction.dx)
        angle = math.atan2(forward[1], forward[0])

        head_x, head_y = self._cell_center(head_cell)
        cx, cy = head_x + offset[0], head_y + offset[1]
        head_radius = settings.CELL_SIZE // 2 + 4

        pygame.draw.circle(surface, colors["outline"], (cx, cy), head_radius + 2)
        pygame.draw.circle(surface, colors["head"], (cx, cy), head_radius)

        if self.world.game_over:
            self._render_dazed_face(surface, (cx, cy), forward, perp, head_radius)
            return

        if self.world.mouth_open:
            mouth_half_angle = math.radians(28)
            jaw_left = (
                cx + math.cos(angle - mouth_half_angle) * head_radius,
                cy + math.sin(angle - mouth_half_angle) * head_radius,
            )
            jaw_right = (
                cx + math.cos(angle + mouth_half_angle) * head_radius,
                cy + math.sin(angle + mouth_half_angle) * head_radius,
            )
            pygame.draw.polygon(surface, colors["mouth"], [(cx, cy), jaw_left, jaw_right])

        eye_forward = head_radius * 0.3
        eye_side = head_radius * 0.5
        eye_radius = max(2, settings.CELL_SIZE // 7)
        pupil_radius = max(1, eye_radius // 2)

        for sign in (1, -1):
            eye_x = cx + forward[0] * eye_forward + perp[0] * eye_side * sign
            eye_y = cy + forward[1] * eye_forward + perp[1] * eye_side * sign
            pygame.draw.circle(surface, colors["eye_white"], (eye_x, eye_y), eye_radius)

            pupil_x = eye_x + forward[0] * eye_radius * 0.4
            pupil_y = eye_y + forward[1] * eye_radius * 0.4
            pygame.draw.circle(surface, colors["eye_pupil"], (pupil_x, pupil_y), pupil_radius)

        if self.world.tongue_flicking:
            self._render_tongue(surface, (cx, cy), forward, perp, head_radius)

    def _render_dazed_face(
        self,
        surface: pygame.Surface,
        head_center: Tuple[float, float],
        forward: Tuple[int, int],
        perp: Tuple[int, int],
        head_radius: float,
    ) -> None:
        colors = settings.SNAKE_COLORS
        cx, cy = head_center

        eye_forward = head_radius * 0.3
        eye_side = head_radius * 0.5
        span = max(3, settings.CELL_SIZE // 6)

        for sign in (1, -1):
            eye_x = cx + forward[0] * eye_forward + perp[0] * eye_side * sign
            eye_y = cy + forward[1] * eye_forward + perp[1] * eye_side * sign
            pygame.draw.line(
                surface, colors["eye_pupil"], (eye_x - span, eye_y - span), (eye_x + span, eye_y + span), 2
            )
            pygame.draw.line(
                surface, colors["eye_pupil"], (eye_x - span, eye_y + span), (eye_x + span, eye_y - span), 2
            )

        mouth_x = cx + forward[0] * head_radius * 0.6
        mouth_y = cy + forward[1] * head_radius * 0.6
        mouth_radius = max(2, settings.CELL_SIZE // 8)
        pygame.draw.circle(surface, colors["mouth"], (mouth_x, mouth_y), mouth_radius)

    def _render_tongue(
        self,
        surface: pygame.Surface,
        head_center: Tuple[float, float],
        forward: Tuple[int, int],
        perp: Tuple[int, int],
        head_radius: float,
    ) -> None:
        colors = settings.SNAKE_COLORS
        cx, cy = head_center

        # world.tongue_progress runs 0 -> 1 over the flick's lifetime;
        # sin(progress * pi) shapes that into out-then-back-in rather
        # than snapping straight to full length.
        flick = math.sin(self.world.tongue_progress * math.pi)
        tongue_len = settings.CELL_SIZE * (0.25 + 0.45 * flick)
        fork_len = settings.CELL_SIZE * 0.18

        tip = (cx + forward[0] * head_radius, cy + forward[1] * head_radius)
        tongue_end = (tip[0] + forward[0] * tongue_len, tip[1] + forward[1] * tongue_len)

        pygame.draw.line(surface, colors["tongue"], tip, tongue_end, 2)

        for sign in (1, -1):
            fork_end = (
                tongue_end[0] + (forward[0] * 0.7 + perp[0] * 0.7 * sign) * fork_len,
                tongue_end[1] + (forward[1] * 0.7 + perp[1] * 0.7 * sign) * fork_len,
            )
            pygame.draw.line(surface, colors["tongue"], tongue_end, fork_end, 2)

    def _render_impact_stars(self, surface: pygame.Surface) -> None:
        impact_cell = self.world.impact_cell

        if impact_cell is None:
            return

        # The impact cell can sit just outside the grid (a wall hit),
        # so clamp it back in before turning it into pixels.
        x, y = impact_cell
        clamped_cell = (
            max(0, min(self.world.grid_cols - 1, x)),
            max(0, min(self.world.grid_rows - 1, y)),
        )
        center = self._cell_center(clamped_cell)
        t = self.world.impact_time

        for i in range(settings.STAR_COUNT):
            orbit_angle = t * settings.STAR_ORBIT_SPEED + i * (2 * math.pi / settings.STAR_COUNT)
            star_center = (
                center[0] + math.cos(orbit_angle) * settings.STAR_ORBIT_RADIUS,
                center[1] + math.sin(orbit_angle) * settings.STAR_ORBIT_RADIUS,
            )
            spin = t * settings.STAR_SPIN_SPEED + i
            self._draw_star(surface, star_center, settings.STAR_SIZE, spin)

    @staticmethod
    def _draw_star(
        surface: pygame.Surface, center: Tuple[float, float], size: float, rotation: float
    ) -> None:
        outer_radius = size
        inner_radius = size * 0.45
        points = []

        for i in range(8):
            angle = rotation + i * math.pi / 4
            radius = outer_radius if i % 2 == 0 else inner_radius
            points.append(
                (center[0] + math.cos(angle) * radius, center[1] + math.sin(angle) * radius)
            )

        pygame.draw.polygon(surface, settings.STAR_COLOR, points)
        pygame.draw.polygon(surface, settings.STAR_OUTLINE, points, 1)

    def _render_food(self, surface: pygame.Surface) -> None:
        for apple in self.world.food_field.apples:
            surface.blit(settings.SPRITES["apple"], self._cell_topleft(apple.position))

            if self.world.mode == "challenge":
                self._render_apple_value_badge(surface, apple)

    def _render_apple_value_badge(self, surface: pygame.Surface, apple) -> None:
        """
        Challenge mode only: a small ring colored by the apple's value tier
        (settings.CHALLENGE_APPLE_VALUE_COLORS) plus its signed value, so the
        filter range shown in the HUD can be checked against something
        visible on the board -- independent of whether the eat/reject logic
        has been implemented yet.
        """
        color = settings.CHALLENGE_APPLE_VALUE_COLORS.get(apple.value, pygame.Color("white"))
        cx, cy = self._cell_center(apple.position)
        pygame.draw.circle(surface, color, (cx, cy), settings.CELL_SIZE // 2 + 3, 2)

        render_text(
            surface,
            f"{apple.value:+d}",
            settings.FONTS["hud"],
            cx,
            cy - settings.CELL_SIZE,
            color,
            center=True,
            shadowed=True,
        )

    def _render_hud(self, surface: pygame.Surface) -> None:
        score_text = f"Manzanas: {self.world.score}"
        render_text(
            surface,
            score_text,
            settings.FONTS["hud"],
            8,
            6,
            pygame.Color("white"),
            shadowed=True,
        )

        self._render_record_badge(surface, score_text)

        if self.world.mode == "challenge":
            render_text(
                surface,
                f"Filtro activo: [{self.world.filter_min}, {self.world.filter_max}]",
                settings.FONTS["hud"],
                8,
                24,
                pygame.Color("white"),
                shadowed=True,
            )
            # Live readout of World.count_apples_in_range() (A01) -- lets
            # the player check the running count against what they can
            # see on the board themselves. `or 0` covers it still being a
            # TODO stub (returns None) so the HUD reads "0/N" instead of
            # the confusing "None/N" until it's implemented.
            total_apples = len(self.world.food_field.apples)
            count_in_range = self.world.count_apples_in_range() or 0
            render_text(
                surface,
                f"En rango: {count_in_range}/{total_apples}",
                settings.FONTS["hud"],
                8,
                42,
                pygame.Color("white"),
                shadowed=True,
            )

    def _render_record_badge(self, surface: pygame.Surface, score_text: str) -> None:
        """
        Draws the pixel-art trophy plus the current best score right after
        the "Manzanas" counter, so the record is always visible next to the
        live count -- see World.display_best_score for how that number is
        picked.
        """
        hud_font = settings.FONTS["hud"]
        score_width, score_height = hud_font.size(score_text)

        trophy = settings.SPRITES["trophy"]
        gap = 6
        trophy_x = 8 + score_width + gap
        trophy_y = 6 + score_height // 2 - trophy.get_height() // 2
        surface.blit(trophy, (trophy_x, trophy_y))

        render_text(
            surface,
            str(self.world.display_best_score),
            hud_font,
            trophy_x + trophy.get_width() + 4,
            6,
            pygame.Color(255, 193, 7),
            shadowed=True,
        )

    # Labels for PlayState's _GAME_OVER_OPTIONS ("restart", "menu"), in the
    # same order -- kept here since this module owns everything drawn on
    # screen, while PlayState owns which one is selected/confirmed.
    _GAME_OVER_LABELS = ("Volver a jugar", "Menu principal")

    def _render_game_over(
        self, surface: pygame.Surface, awaiting_record_name: bool, selected_index: int
    ) -> None:
        center_x = settings.VIRTUAL_WIDTH // 2
        center_y = settings.VIRTUAL_HEIGHT // 2

        render_text(
            surface,
            "GAME OVER",
            settings.FONTS["title"],
            center_x,
            center_y - 12,
            settings.UI_TEXT_COLOR,
            center=True,
            shadowed=True,
        )

        # While PlayState has the new-record name prompt up, ENTER submits
        # the name rather than confirming a button -- skip the buttons
        # below so they don't contradict what the key is about to do.
        if awaiting_record_name:
            return

        for i, label in enumerate(self._GAME_OVER_LABELS):
            selected = i == selected_index
            color = settings.UI_ACCENT_COLOR if selected else settings.UI_TEXT_COLOR
            prefix = "> " if selected else "  "
            render_text(
                surface,
                prefix + label,
                settings.FONTS["hud"],
                center_x,
                center_y + 16 + i * 20,
                color,
                center=True,
                shadowed=True,
            )

        render_text(
            surface,
            "Flechas arriba/abajo para elegir, ENTER para confirmar",
            settings.FONTS["hud"],
            center_x,
            center_y + 16 + len(self._GAME_OVER_LABELS) * 20 + 8,
            settings.UI_TEXT_COLOR,
            center=True,
            shadowed=True,
        )
