"""
Modulo A - Motor del tablero.

This file contains the class Board and MatchRun. Board owns the tile
matrix, generates tiles without pre-existing matches, finds runs of 3+
same-kind tiles (horizontal and vertical), resolves them (including
the Match-4 Catalysis rule, which clears the whole line instead of
just the run), and computes gravity for the tiles that fall to fill
the gaps.

This module knows nothing about HP, essence, or turns -- it only
reports which TileKind was cleared and how many times, plus whether a
catalysis happened. Translating that into combat effects is the job of
src.combat.combat_controller (Modulo C).
"""

import random

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

import pygame

import settings
from src.board.tile import Tile, TileKind


@dataclass
class MatchRun:
    kind: TileKind
    tiles: List[Tile]
    orientation: str  # "h" or "v"
    line_index: int

    @property
    def is_catalysis(self) -> bool:
        return len(self.tiles) >= 4


class Board:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y
        self.tiles: List[List[Optional[Tile]]] = []
        self._initialize_tiles()

    def render(self, surface: pygame.Surface) -> None:
        for row in self.tiles:
            for tile in row:
                if tile is not None:
                    tile.render(surface, self.x, self.y)

    # -- Initialization -----------------------------------------------

    def _random_kind(self) -> TileKind:
        return random.choice(list(TileKind))

    def _is_match_generated(self, i: int, j: int, kind: TileKind) -> bool:
        if (
            i >= 2
            and self.tiles[i - 1][j].kind == kind
            and self.tiles[i - 2][j].kind == kind
        ):
            return True

        return (
            j >= 2
            and self.tiles[i][j - 1].kind == kind
            and self.tiles[i][j - 2].kind == kind
        )

    def _initialize_tiles(self) -> None:
        self.tiles = [
            [None for _ in range(settings.BOARD_WIDTH)] for _ in range(settings.BOARD_HEIGHT)
        ]
        for i in range(settings.BOARD_HEIGHT):
            for j in range(settings.BOARD_WIDTH):
                kind = self._random_kind()
                while self._is_match_generated(i, j, kind):
                    kind = self._random_kind()
                self.tiles[i][j] = Tile(i, j, kind)

    # -- Match detection -------------------------------------------------

    def find_matches(self) -> List[MatchRun]:
        """
        Scans the whole board for horizontal and vertical runs of 3 or
        more same-kind tiles. A tile that belongs to both a horizontal
        and a vertical run (an L/T shape) is reported in both runs --
        each run is a distinct match that Modulo C will reward on its
        own, same as in classic match-3 games.
        """
        runs: List[MatchRun] = []

        for i in range(settings.BOARD_HEIGHT):
            j = 0
            while j < settings.BOARD_WIDTH:
                kind = self.tiles[i][j].kind
                start = j
                while j + 1 < settings.BOARD_WIDTH and self.tiles[i][j + 1].kind == kind:
                    j += 1
                length = j - start + 1
                if length >= 3:
                    tiles = [self.tiles[i][jj] for jj in range(start, j + 1)]
                    runs.append(MatchRun(kind, tiles, "h", i))
                j += 1

        for j in range(settings.BOARD_WIDTH):
            i = 0
            while i < settings.BOARD_HEIGHT:
                kind = self.tiles[i][j].kind
                start = i
                while i + 1 < settings.BOARD_HEIGHT and self.tiles[i + 1][j].kind == kind:
                    i += 1
                length = i - start + 1
                if length >= 3:
                    tiles = [self.tiles[ii][j] for ii in range(start, i + 1)]
                    runs.append(MatchRun(kind, tiles, "v", j))
                i += 1

        return runs

    # -- Resolution --------------------------------------------------------

    def resolve_runs(
        self, runs: List[MatchRun]
    ) -> Tuple[Dict[TileKind, int], bool, int]:
        """
        Clears every run from the board. A run of length >= 4 (Regla de
        Catalisis) additionally clears every remaining tile on its full
        row/column, whatever kind they are.

        :returns: (kind_counts, catalysis_triggered, total_tiles_cleared)
        kind_counts maps each TileKind to how many tiles of that kind
        were cleared (used by Modulo C to compute damage/essence).
        """
        cleared: Set[Tile] = set()
        kind_counts: Dict[TileKind, int] = {kind: 0 for kind in TileKind}
        catalysis = False

        for run in runs:
            for tile in run.tiles:
                if tile not in cleared:
                    cleared.add(tile)
                    kind_counts[tile.kind] += 1

            if run.is_catalysis:
                catalysis = True
                if run.orientation == "h":
                    line_tiles = [self.tiles[run.line_index][j] for j in range(settings.BOARD_WIDTH)]
                else:
                    line_tiles = [self.tiles[i][run.line_index] for i in range(settings.BOARD_HEIGHT)]

                for tile in line_tiles:
                    if tile is not None and tile not in cleared:
                        cleared.add(tile)
                        kind_counts[tile.kind] += 1

        for tile in cleared:
            self.tiles[tile.i][tile.j] = None

        return kind_counts, catalysis, len(cleared)

    # -- Gravity -------------------------------------------------------

    def get_falling_tiles(self) -> List[Tuple[Tile, Dict[str, Any]]]:
        tweens: List[Tuple[Tile, Dict[str, Any]]] = []

        for j in range(settings.BOARD_WIDTH):
            space = False
            space_i = -1
            i = settings.BOARD_HEIGHT - 1

            while i >= 0:
                tile = self.tiles[i][j]

                if space:
                    if tile is not None:
                        self.tiles[space_i][j] = tile
                        tile.i = space_i
                        self.tiles[i][j] = None
                        tweens.append((tile, {"y": tile.i * settings.TILE_SIZE}))
                        space = False
                        i = space_i
                        space_i = -1
                elif tile is None:
                    space = True
                    if space_i == -1:
                        space_i = i

                i -= 1

        for j in range(settings.BOARD_WIDTH):
            for i in range(settings.BOARD_HEIGHT):
                tile = self.tiles[i][j]

                if tile is None:
                    tile = Tile(i, j, self._random_kind())
                    tile.y -= settings.TILE_SIZE
                    self.tiles[i][j] = tile
                    tweens.append((tile, {"y": tile.i * settings.TILE_SIZE}))

        return tweens
