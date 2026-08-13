"""
3D rendering of the Rubik's Cube: projects the cube's 6 faces (each
with its 3x3 grid of "stickers") onto the screen, rotated according to
two angles (yaw/pitch) controlled by the player, with simple
perspective, backface culling, and depth sorting (painter's
algorithm).

This module is purely about drawing: it contains no cube logic of its
own -- that lives in `src/rubik_cube.py`. By importing pygame, it
stays separate from `src/algorithm.py` and `src/rubik_cube.py`, which
are pure logic.

Each sticker's color comes from `cube.colors` (position + outward
direction -> color), which travels with the piece when a layer turns
-- see `RubikCube._rotate_layer_colors` in `src/rubik_cube.py` --, so
turning or scrambling the cube actually changes the visible colors,
just like on a real cube.
"""
import math
from typing import Callable, FrozenSet, List, NamedTuple, Optional, Set, Tuple

import pygame
import pygame.gfxdraw

from src.rubik_cube import SIZE, RubikCube

Point3D = Tuple[float, float, float]
Point2D = Tuple[float, float]
Indices = Tuple[int, int, int]
Color = Tuple[int, int, int]


class LayerAnimation(NamedTuple):
    """
    Describes a layer turn in progress, halfway between its starting
    angle (not turned) and final angle (90 degrees): `draw_cube_3d`
    uses it to visually rotate only that layer's pieces while the
    animation advances, without touching `cube.matrix`/`cube.colors`
    -- the actual move is applied only once, right when the animation
    finishes (see `src/states/play_state.py`).
    """

    axis: str  # 'x', 'y' or 'z' -- same meaning as in RubikCube.rotate_layer
    indices: FrozenSet[int]  # which layer(s) of that axis are turning (one, or two for a wide-layer turn)
    clockwise: bool
    progress: float  # 0.0 (just starting) .. 1.0 (90-degree turn complete)

# Distance (in cube units) from the camera to the origin, along +Z,
# looking towards the origin: controls how much perspective is seen
# (a large value approaches a "flat" orthographic projection; a small
# one exaggerates the depth effect).
CAMERA_DISTANCE = 6.0

# How "open" the corner rounding of a sticker is, as a fraction of the
# cube's scale (see `_round_corners`): higher = rounder corners. It's
# a pixel size relative to `scale`, not a fraction of each edge -- so
# a very elongated cell on screen (for instance, a face seen almost
# edge-on) doesn't end up with a sharp corner entirely "eaten" by the
# rounding.
CORNER_RADIUS_FACTOR = 0.13

# Safety cap: a corner's rounding never cuts more than this fraction
# of any edge that reaches it, so two neighboring cuts (one from each
# end of an edge) never cross each other, even on very small or very
# thin cells.
EDGE_CUT_CAP = 0.4

# How many straight segments approximate each rounded corner's curve:
# higher = smoother curve (and more points per polygon).
SEGMENTS_PER_CORNER = 4


def _point_near(vertex: Point2D, neighbor: Point2D, factor: float) -> Point2D:
    """Point located `factor` (0..1) of the way from `vertex` towards `neighbor`."""
    return (
        vertex[0] + (neighbor[0] - vertex[0]) * factor,
        vertex[1] + (neighbor[1] - vertex[1]) * factor,
    )


def _quadratic_bezier_point(p0: Point2D, p1: Point2D, p2: Point2D, t: float) -> Point2D:
    """Point at fraction `t` (0..1) of the quadratic Bézier curve p0-p1-p2."""
    x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t**2 * p2[0]
    y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t**2 * p2[1]
    return (x, y)


def _round_corners(points: List[Point2D], radius_px: float) -> List[Point2D]:
    """
    Smooths the corners of a convex polygon: at each vertex, it cuts
    towards its two neighbors and replaces the sharp corner with a
    quadratic Bézier curve that uses the original vertex as its
    control point. Produces a rounded outline instead of sharp
    corners, so each sticker looks more polished/crisp on screen.

    The cut towards each neighbor aims for `radius_px` pixels, but
    never more than `EDGE_CUT_CAP` of that particular edge -- so a
    short edge (for instance, a cell seen almost edge-on, very
    elongated) doesn't get entirely cut away by aiming for a radius
    meant for normal edges.
    """
    count = len(points)
    result: List[Point2D] = []

    for i in range(count):
        previous = points[i - 1]
        current = points[i]
        next_point = points[(i + 1) % count]

        previous_length = math.hypot(previous[0] - current[0], previous[1] - current[1])
        next_length = math.hypot(next_point[0] - current[0], next_point[1] - current[1])

        previous_factor = (
            min(radius_px, previous_length * EDGE_CUT_CAP) / previous_length
            if previous_length > 0
            else 0.0
        )
        next_factor = (
            min(radius_px, next_length * EDGE_CUT_CAP) / next_length
            if next_length > 0
            else 0.0
        )

        curve_start = _point_near(current, previous, previous_factor)
        curve_end = _point_near(current, next_point, next_factor)

        for step in range(SEGMENTS_PER_CORNER + 1):
            t = step / SEGMENTS_PER_CORNER
            result.append(_quadratic_bezier_point(curve_start, current, curve_end, t))

    return result


def _local_coordinate(index: int) -> float:
    """Converts a grid index (0, 1, 2) into its centered local coordinate (-1, 0, 1)."""
    return index - 1.0


def rotate_point(point: Point3D, yaw: float, pitch: float) -> Point3D:
    """
    Rotates a 3D point first around the Y axis (yaw, "turn the camera
    sideways") and then around the already-rotated X axis (pitch,
    "turn the camera up/down").
    """
    x, y, z = point

    # --- Step 1: rotation around the Y axis (yaw) ----------------------
    x1 = x * math.cos(yaw) + z * math.sin(yaw)
    z1 = -x * math.sin(yaw) + z * math.cos(yaw)
    y1 = y

    # --- Step 2: rotation around the X axis (pitch) ---------------------
    y2 = y1 * math.cos(pitch) - z1 * math.sin(pitch)
    z2 = y1 * math.sin(pitch) + z1 * math.cos(pitch)
    x2 = x1

    return (x2, y2, z2)


_AXIS_INDEX = {"x": 0, "y": 1, "z": 2}


def _rotate_point_in_layer(point: Point3D, axis: str, angle: float) -> Point3D:
    """
    Rotates a 3D point by an arbitrary angle (in radians) around
    `axis`, with the same orientation `RubikCube._rotate_sticker`/
    `_rotate_pair` (src/rubik_cube.py) use for a discrete 90-degree
    turn: there, clockwise equals a -90 degree angle with this same
    formula, for any of the 3 axes (`_rotate_pair` doesn't care about
    the axis, it only operates on the pair of coordinates
    perpendicular to it). Used to continuously animate (`angle`
    between 0 and ±90 degrees) what those functions only give
    discretely -- see `_animation_angle`.
    """
    x, y, z = point
    cos_a, sin_a = math.cos(angle), math.sin(angle)

    if axis == "x":
        a, b = y, z
    elif axis == "y":
        a, b = x, z
    else:  # axis == "z"
        a, b = x, y

    a2 = a * cos_a - b * sin_a
    b2 = a * sin_a + b * cos_a

    if axis == "x":
        return (x, a2, b2)
    if axis == "y":
        return (a2, y, b2)
    return (a2, b2, z)


def _animation_angle(animation: LayerAnimation) -> float:
    """Angle (in radians) an animation has already turned, based on its progress (0..1) and direction."""
    max_angle = (math.pi / 2) * animation.progress
    return -max_angle if animation.clockwise else max_angle


def _project(rotated_point: Point3D, center: Point2D, scale: float) -> Point2D:
    """
    Projects an already-rotated 3D point to 2D screen coordinates,
    with simple perspective: points closer to the camera (larger z)
    look bigger; farther ones (smaller z), smaller.
    """
    x, y, z = rotated_point
    factor = CAMERA_DISTANCE / (CAMERA_DISTANCE - z)
    screen_x = center[0] + x * scale * factor
    screen_y = center[1] - y * scale * factor
    return (screen_x, screen_y)


# Each entry describes one of the big cube's 6 outer faces: its name,
# its normal (in local, unrotated coordinates), a function that
# translates a cell (u, v) of its 3x3 grid into RubikCube.matrix
# indices (x, y, z), and another that gives that cell's 4 local
# corners.
_FaceDescriptor = Tuple[
    str,
    Point3D,
    Callable[[int, int], Indices],
    Callable[[int, int], List[Point3D]],
]


def _describe_faces() -> List[_FaceDescriptor]:
    def corners(cx: float, cy: float, cz: float, fixed_axis: str) -> List[Point3D]:
        if fixed_axis == "x":
            return [
                (cx, cy - 0.5, cz - 0.5),
                (cx, cy + 0.5, cz - 0.5),
                (cx, cy + 0.5, cz + 0.5),
                (cx, cy - 0.5, cz + 0.5),
            ]
        if fixed_axis == "y":
            return [
                (cx - 0.5, cy, cz - 0.5),
                (cx + 0.5, cy, cz - 0.5),
                (cx + 0.5, cy, cz + 0.5),
                (cx - 0.5, cy, cz + 0.5),
            ]
        # fixed_axis == "z"
        return [
            (cx - 0.5, cy - 0.5, cz),
            (cx + 0.5, cy - 0.5, cz),
            (cx + 0.5, cy + 0.5, cz),
            (cx - 0.5, cy + 0.5, cz),
        ]

    return [
        (
            "Up",
            (0.0, 1.0, 0.0),
            lambda u, v: (u, 2, v),
            lambda u, v: corners(_local_coordinate(u), 1.5, _local_coordinate(v), "y"),
        ),
        (
            "Down",
            (0.0, -1.0, 0.0),
            lambda u, v: (u, 0, v),
            lambda u, v: corners(_local_coordinate(u), -1.5, _local_coordinate(v), "y"),
        ),
        (
            "Right",
            (1.0, 0.0, 0.0),
            lambda u, v: (2, u, v),
            lambda u, v: corners(1.5, _local_coordinate(u), _local_coordinate(v), "x"),
        ),
        (
            "Left",
            (-1.0, 0.0, 0.0),
            lambda u, v: (0, u, v),
            lambda u, v: corners(-1.5, _local_coordinate(u), _local_coordinate(v), "x"),
        ),
        (
            "Front",
            (0.0, 0.0, 1.0),
            lambda u, v: (u, v, 2),
            lambda u, v: corners(_local_coordinate(u), _local_coordinate(v), 1.5, "z"),
        ),
        (
            "Back",
            (0.0, 0.0, -1.0),
            lambda u, v: (u, v, 0),
            lambda u, v: corners(_local_coordinate(u), _local_coordinate(v), -1.5, "z"),
        ),
    ]


_FACES = _describe_faces()

# Move letter (see `layers_for_move` in src/rubik_cube.py) that
# corresponds to each face, for the guide toggled by the "eye" button
# (see `draw_face_guide` and `PlayState._draw_eye_button`).
_LETTER_BY_FACE = {
    "Up": "U",
    "Down": "D",
    "Right": "R",
    "Left": "L",
    "Front": "F",
    "Back": "B",
}

GUIDE_LABEL_BACKGROUND_COLOR = (255, 255, 255)
GUIDE_LABEL_BORDER_COLOR = (18, 18, 22)
GUIDE_LABEL_RADIUS = 8  # px, at virtual screen scale (see settings.VIRTUAL_WIDTH/HEIGHT)

# How far from the cube's center each label is placed, in cube units:
# 1.5 is the face surface itself (same value used by its cells'
# corners in `_describe_faces`); a larger value separates it from the
# surface so it reads as a guide floating above the cube, not as just
# another sticker.
GUIDE_LABEL_DISTANCE = 2.3


def draw_face_guide(
    surface: pygame.Surface,
    yaw: float,
    pitch: float,
    center: Point2D,
    scale: float,
    font: pygame.font.Font,
) -> None:
    """
    Draws, over the center of every cube face currently facing the
    camera, a circle with its move letter (U/D/L/R/F/B) -- a guide for
    the player, shown only while the "eye" button is in its open state
    (see `PlayState._draw_eye_button`).

    Each letter stays aligned with the physically correct face (not a
    fixed screen position) because it is projected along that face's
    local normal -- see `GUIDE_LABEL_DISTANCE` -- with the same
    yaw/pitch as the rest of the cube, so it turns along with it while
    dragging the camera; it is placed farther out than the surface
    itself so it reads as separated from the cube, floating.
    """
    for name, normal, _index_fn, _corner_fn in _FACES:
        rotated_normal = rotate_point(normal, yaw, pitch)
        if rotated_normal[2] <= 0.05:
            continue  # face looking away: not visible, skip its letter

        face_center = (
            normal[0] * GUIDE_LABEL_DISTANCE,
            normal[1] * GUIDE_LABEL_DISTANCE,
            normal[2] * GUIDE_LABEL_DISTANCE,
        )
        point_2d = _project(rotate_point(face_center, yaw, pitch), center, scale)
        _draw_guide_label(surface, point_2d, _LETTER_BY_FACE[name], font)


def _draw_guide_label(
    surface: pygame.Surface, point: Point2D, letter: str, font: pygame.font.Font
) -> None:
    x, y = round(point[0]), round(point[1])
    pygame.gfxdraw.filled_circle(surface, x, y, GUIDE_LABEL_RADIUS, GUIDE_LABEL_BACKGROUND_COLOR)
    pygame.gfxdraw.aacircle(surface, x, y, GUIDE_LABEL_RADIUS, GUIDE_LABEL_BORDER_COLOR)

    text = font.render(letter, True, GUIDE_LABEL_BORDER_COLOR)
    surface.blit(text, text.get_rect(center=(x, y)))


def draw_cube_3d(
    surface: pygame.Surface,
    cube: RubikCube,
    yaw: float,
    pitch: float,
    center: Point2D,
    scale: float,
    highlight: Optional[Set[Indices]] = None,
    animation: Optional[LayerAnimation] = None,
) -> None:
    """
    Draws the whole cube in 3D onto `surface`.

    Algorithm, step by step, for each of the 54 cells (9 per each of
    the 6 faces):
        1. If `animation` is not None and this cell belongs to the
           layer that is turning (same coordinate, on the animation's
           axis, as one of its `indices`), its position (and its
           normal) is rotated by an intermediate angle around that
           axis -- see `_rotate_point_in_layer` -- before the camera
           is applied. The rest of the cells are unaffected.
        2. The cell's normal (animated or not) is rotated with the
           same yaw/pitch as the rest of the scene.
        3. Backface culling, cell by cell (not per whole face: an
           animated cell can end up facing the other way before the
           rest of its original face does): if the rotated normal
           doesn't point towards the camera (which looks from +Z),
           that cell is not drawn.
        4. Of the cells that are visible, their depth (Z coordinate
           after rotation) is computed and they are sorted from
           farthest to nearest ("painter's algorithm"), so a near cell
           never ends up covered by a far one.
        5. Each cell is projected to 2D and filled with the color
           `cube.colors` has stored for its *original* position and
           direction (unanimated: while the animation is in progress,
           the move hasn't actually been applied yet -- see
           `src/states/play_state.py`); if that position is part of a
           highlighted A03 search result, its border is drawn white
           and thicker.

    :param cube: The cube whose state (`cube.colors`) is drawn.
    :param yaw: Horizontal rotation angle, in radians.
    :param pitch: Vertical rotation angle, in radians.
    :param center: Screen point (x, y) the cube's center is projected onto.
    :param scale: Pixels per cube unit (controls the on-screen size).
    :param highlight: Optional set of `cube.matrix` positions (x, y, z) to highlight (for instance, an A03 search result).
    :param animation: Layer turn in progress to animate (see `LayerAnimation`), or None to draw the cube at rest.
    """
    corner_radius_px = scale * CORNER_RADIUS_FACTOR

    animation_angle = 0.0
    animated_axis_index = -1
    if animation is not None:
        animation_angle = _animation_angle(animation)
        animated_axis_index = _AXIS_INDEX[animation.axis]

    visible_cells = []

    for _name, normal, index_fn, corner_fn in _FACES:
        for u in range(SIZE):
            for v in range(SIZE):
                indices = index_fn(u, v)
                corners = corner_fn(u, v)
                cell_normal = normal

                # Step 1: animate this cell if its layer is turning.
                if animation is not None and indices[animated_axis_index] in animation.indices:
                    corners = [
                        _rotate_point_in_layer(p, animation.axis, animation_angle) for p in corners
                    ]
                    cell_normal = _rotate_point_in_layer(cell_normal, animation.axis, animation_angle)

                # Step 2-3: camera and backface culling.
                rotated_normal = rotate_point(cell_normal, yaw, pitch)
                if rotated_normal[2] <= 0.05:
                    continue

                direction = (round(normal[0]), round(normal[1]), round(normal[2]))
                color = cube.colors[indices + (direction,)]

                rotated_corners = [rotate_point(p, yaw, pitch) for p in corners]
                depth = sum(p[2] for p in rotated_corners) / 4.0
                visible_cells.append((depth, color, rotated_corners, indices))

    # Step 4: painter's algorithm -- from farthest cell (smallest Z) to nearest.
    visible_cells.sort(key=lambda cell: cell[0])

    for _depth, color, rotated_corners, indices in visible_cells:
        points_2d = [_project(p, center, scale) for p in rotated_corners]
        outline = _round_corners(points_2d, corner_radius_px)
        int_outline = [(round(px), round(py)) for px, py in outline]

        # Fill + antialiased outline (gfxdraw) instead of
        # pygame.draw.polygon: together with the corner rounding, it
        # avoids "stair-stepped" edges and gives a crisper image.
        pygame.gfxdraw.filled_polygon(surface, int_outline, color)
        pygame.gfxdraw.aapolygon(surface, int_outline, color)

        highlighted = highlight is not None and indices in highlight
        border_color = (255, 255, 255) if highlighted else (18, 18, 22)
        pygame.gfxdraw.aapolygon(surface, int_outline, border_color)
        if highlighted:
            pygame.draw.polygon(surface, border_color, int_outline, 2)
