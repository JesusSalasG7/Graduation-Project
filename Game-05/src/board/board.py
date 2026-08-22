"""
Modulo A - Motor del tablero.

This file contains the class Board and MatchRun. Board owns the tile
matrix, generates tiles without pre-existing matches, finds runs of 3+
same-kind tiles (horizontal and vertical), resolves them (including
the Match-4 Catalysis rule, which clears the whole line instead of
just the run), and computes gravity for the tiles that fall to fill
the gaps.

This module knows nothing about score or turns -- it only reports
which TileKind was cleared and how many times, whether a catalysis
happened, and how many distinct kinds a catalysis line carried (via
src.algorithm.remove_duplicates -- Desafio A05). Translating that into
score/feedback is the job of src.states.play_state.
"""

import random

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

import pygame

import settings
from src.algorithm import remove_duplicates
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
        # _initialize_tiles only guarantees no match exists yet -- it
        # says nothing about whether the player can ever *make* one.
        # Keep re-rolling the whole board until at least one swap
        # would produce a match, so we never hand out a dead board.
        while not self.has_possible_moves():
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

    # -- Deadlock detection --------------------------------------------

    def _swap_would_match(self, i1: int, j1: int, i2: int, j2: int) -> bool:
        # Swap just the two tiles' kind (not their i/j/x/y, which the
        # rest of the board relies on for position), check, then
        # revert -- a cheap way to try a move without disturbing state.
        t1, t2 = self.tiles[i1][j1], self.tiles[i2][j2]
        t1.kind, t2.kind = t2.kind, t1.kind
        matched = bool(self.find_matches())
        t1.kind, t2.kind = t2.kind, t1.kind
        return matched

    def find_hint(self) -> Optional[Tuple[Tuple[int, int], Tuple[int, int]]]:
        """
        Returns the (i, j) coordinates of two adjacent tiles whose swap
        would produce a match, or None if no such swap exists. Used
        both to detect a "dead" board (has_possible_moves below) and,
        by PlayState, to highlight a legal move after a few idle
        seconds -- some valid swaps produce a match nowhere near the
        two tiles moved, so they're easy to miss just by looking.
        """
        for i in range(settings.BOARD_HEIGHT):
            for j in range(settings.BOARD_WIDTH):
                if j + 1 < settings.BOARD_WIDTH and self._swap_would_match(i, j, i, j + 1):
                    return (i, j), (i, j + 1)
                if i + 1 < settings.BOARD_HEIGHT and self._swap_would_match(i, j, i + 1, j):
                    return (i, j), (i + 1, j)
        return None

    def has_possible_moves(self) -> bool:
        """
        True if at least one adjacent swap would produce a match.
        Used to detect a "dead" board (no legal move left after a
        cascade settles) so it can be reshuffled instead of leaving
        the player stuck.
        """
        return self.find_hint() is not None

    def shuffle(self) -> None:
        """
        Reshuffles the kinds currently on the board (tile positions/
        identities don't change) until the result has no pre-existing
        match and at least one legal move -- called when a cascade
        leaves the board dead.
        """
        kinds = [tile.kind for row in self.tiles for tile in row]
        while True:
            random.shuffle(kinds)
            it = iter(kinds)
            for row in self.tiles:
                for tile in row:
                    tile.kind = next(it)
            if not self.find_matches() and self.has_possible_moves():
                return

    # -- Resolution --------------------------------------------------------

    def resolve_runs(
        self, runs: List[MatchRun]
    ) -> Tuple[Dict[TileKind, int], bool, int, int]:
        """
        Clears every run from the board. A run of length >= 4 (Regla de
        Catalisis) additionally clears every remaining tile on its full
        row/column, whatever kind they are.

        :returns: (kind_counts, catalysis_triggered, total_tiles_cleared,
            catalysis_diversity_kinds). kind_counts maps each TileKind
            to how many tiles of that kind were cleared (used by
            Modulo C to compute damage/essence). catalysis_diversity_kinds
            is how many *distinct* element kinds a Catalisis line swept
            this call (Desafio A05 -- see src.algorithm.remove_duplicates),
            0 if no Catalisis triggered.
        """
        cleared: Set[Tile] = set()
        kind_counts: Dict[TileKind, int] = {kind: 0 for kind in TileKind}
        catalysis = False
        catalysis_diversity_kinds = 0

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

                # Desafio A05: la fila/columna completa es una matriz
                # de enteros (una fila, los TileKind.value de cada
                # ficha) -- remove_duplicates dice cuantos elementos
                # realmente distintos arrastro esta Catalisis.
                line_kinds = [[tile.kind.value for tile in line_tiles if tile is not None]]
                catalysis_diversity_kinds += len(remove_duplicates(line_kinds))

                for tile in line_tiles:
                    if tile is not None and tile not in cleared:
                        cleared.add(tile)
                        kind_counts[tile.kind] += 1

        for tile in cleared:
            self.tiles[tile.i][tile.j] = None

        return kind_counts, catalysis, len(cleared), catalysis_diversity_kinds

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
