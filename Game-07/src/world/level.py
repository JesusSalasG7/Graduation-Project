"""
Level: the finished, guaranteed-navigable grid gameplay and rendering
actually read from -- the raw CA matrix (src/world/level_generator.py)
plus a spawn cell, a goal cell, and a scatter of obstacle hazards, all
placed by generate_playable_level rather than something PlayState pieces
together by hand.
"""
import random
from collections import deque
from typing import FrozenSet, List, Set, Tuple

from src.world.level_generator import EMPTY, LevelGenerator, WALL

Grid = List[List[int]]
Cell = Tuple[int, int]  # (row, col)


class Level:
    def __init__(self, grid: Grid, spawn_cell: Cell, goal_cell: Cell, obstacle_cells: FrozenSet[Cell]) -> None:
        self.grid = grid
        self.rows = len(grid)
        self.columns = len(grid[0]) if grid else 0
        self.spawn_row, self.spawn_col = spawn_cell
        self.goal_row, self.goal_col = goal_cell
        self.obstacle_cells = obstacle_cells

    def is_wall(self, row: int, col: int) -> bool:
        """
        True for a solid cell AND for anything outside the grid -- the
        map border always behaves like a wall, so Player never needs its
        own bounds check on top of this one.
        """
        if not (0 <= row < self.rows and 0 <= col < self.columns):
            return True
        return self.grid[row][col] == WALL

    def is_goal(self, row: int, col: int) -> bool:
        return (row, col) == (self.goal_row, self.goal_col)

    def is_obstacle(self, row: int, col: int) -> bool:
        return (row, col) in self.obstacle_cells


def _bfs_distances(grid: Grid, rows: int, columns: int, start: Cell) -> dict:
    """
    Shortest-path distance (in cells, 4-directional) from `start` to
    every cell reachable through EMPTY cells. Used both to find the
    farthest point from spawn (the goal) and to keep obstacles a minimum
    number of steps away from spawn.
    """
    distances = {start: 0}
    queue = deque([start])

    while queue:
        row, col = queue.popleft()
        for delta_row, delta_col in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            neighbor = (row + delta_row, col + delta_col)
            neighbor_row, neighbor_col = neighbor
            if (
                0 <= neighbor_row < rows
                and 0 <= neighbor_col < columns
                and grid[neighbor_row][neighbor_col] == EMPTY
                and neighbor not in distances
            ):
                distances[neighbor] = distances[(row, col)] + 1
                queue.append(neighbor)

    return distances


def _path_exists_avoiding(grid: Grid, rows: int, columns: int, start: Cell, goal: Cell, blocked: Set[Cell]) -> bool:
    """
    Whether `goal` is reachable from `start` through EMPTY cells that
    aren't in `blocked` -- touching an obstacle sends the player straight
    back to spawn (see Player.warp_to / PlayState._on_enter_cell), which
    for reachability purposes makes it act exactly like a wall: there is
    no way to ever stand on its far side. Used to keep obstacle placement
    from ever sealing off the only route to the goal.
    """
    if start in blocked or goal in blocked:
        return False

    visited = {start}
    queue = deque([start])

    while queue:
        row, col = queue.popleft()
        if (row, col) == goal:
            return True

        for delta_row, delta_col in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            neighbor = (row + delta_row, col + delta_col)
            neighbor_row, neighbor_col = neighbor
            if (
                0 <= neighbor_row < rows
                and 0 <= neighbor_col < columns
                and grid[neighbor_row][neighbor_col] == EMPTY
                and neighbor not in visited
                and neighbor not in blocked
            ):
                visited.add(neighbor)
                queue.append(neighbor)

    return False


def _pick_obstacles(
    grid: Grid,
    rows: int,
    columns: int,
    open_cells: List[Cell],
    spawn_cell: Cell,
    goal_cell: Cell,
    distances_from_spawn: dict,
    safe_radius: int,
    density: float,
    rng: random.Random,
) -> FrozenSet[Cell]:
    """
    Scatters hazards over the maze without ever making it unsolvable. A
    single-cell-wide maze corridor is very often the ONLY route between
    two points, so a naive random scatter routinely lands an obstacle on
    a cell every path to the goal has to cross -- since touching one
    sends the player back to spawn, that cell becomes impossible to ever
    get past, and the level has no solution. Adding candidates one at a
    time and keeping only the ones that still leave a spawn->goal route
    open (via _path_exists_avoiding) guarantees a solvable path always
    survives, at the cost of sometimes placing fewer obstacles than
    `density` asks for in a maze with few alternate routes.
    """
    candidates = [
        cell
        for cell in open_cells
        if cell != spawn_cell and cell != goal_cell and distances_from_spawn.get(cell, 0) >= safe_radius
    ]
    rng.shuffle(candidates)
    target_count = round(len(open_cells) * density)

    obstacles: Set[Cell] = set()
    for cell in candidates:
        if len(obstacles) >= target_count:
            break

        obstacles.add(cell)
        if not _path_exists_avoiding(grid, rows, columns, spawn_cell, goal_cell, obstacles):
            obstacles.remove(cell)

    return frozenset(obstacles)


def generate_playable_level(
    columns: int,
    rows: int,
    wall_probability: float,
    iterations: int,
    birth_limit: int,
    survive_min: int,
    survive_max: int,
    min_open_cells: int,
    min_goal_distance: int,
    obstacle_density: float,
    obstacle_safe_radius: int,
    max_attempts: int,
    rng: random.Random = None,
) -> Level:
    """
    Re-rolls LevelGenerator up to max_attempts times, stopping at the
    first result that both has at least min_open_cells and whose
    farthest reachable point from spawn is at least min_goal_distance
    cells away -- an unlucky noise seed can otherwise collapse into a
    pocket too small, or too shallow, to be worth sliding around in.
    Falls back to whichever attempt scored best (open cells, then goal
    distance) if none clear both thresholds, so this always returns
    something playable rather than raising.
    """
    rng = rng or random.Random()
    best_generator = None
    best_score = (-1, -1)
    best_spawn = None
    best_goal = None
    best_distances = None

    for _ in range(max_attempts):
        generator = LevelGenerator(
            columns, rows, wall_probability, iterations, birth_limit, survive_min, survive_max, rng=rng
        )
        generator.generate()

        spawn_cell = generator.pick_spawn_cell()
        distances = _bfs_distances(generator.grid, rows, columns, spawn_cell)
        goal_cell = max(distances, key=distances.get)
        goal_distance = distances[goal_cell]

        score = (len(generator.largest_region), goal_distance)
        if score > best_score:
            best_score = score
            best_generator = generator
            best_spawn = spawn_cell
            best_goal = goal_cell
            best_distances = distances

        if len(generator.largest_region) >= min_open_cells and goal_distance >= min_goal_distance:
            break

    obstacle_cells = _pick_obstacles(
        best_generator.grid,
        rows,
        columns,
        best_generator.largest_region,
        best_spawn,
        best_goal,
        best_distances,
        obstacle_safe_radius,
        obstacle_density,
        rng,
    )

    return Level(best_generator.grid, best_spawn, best_goal, obstacle_cells)
