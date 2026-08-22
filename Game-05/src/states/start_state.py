"""
This file contains the class StartState: the main menu.
"""

import random

import pygame

from gale.input_handler import InputData
from gale.state import BaseState, StateMachine
from gale.text import render_text
from gale.timer import Timer

import settings
from src.board.tile import Tile, TileKind


class StartState(BaseState):
    def __init__(self, state_machine: StateMachine, game) -> None:
        super().__init__(state_machine)
        self.game = game

    def enter(self) -> None:
        self.current_menu_item = 1
        self.active = True
        self.alpha_transition = 0

        # Decorative row of placeholder tiles behind the title, using
        # the same procedural placeholders the board uses.
        self.deco_tiles = []
        cols = settings.VIRTUAL_WIDTH // settings.TILE_SIZE
        rows = 4
        for i in range(rows):
            for j in range(cols):
                tile = Tile(i, j, random.choice(list(TileKind)))
                self.deco_tiles.append(tile)

        self.screen_alpha_surface = pygame.Surface(
            (settings.VIRTUAL_WIDTH, settings.VIRTUAL_HEIGHT), pygame.SRCALPHA
        )

    def render(self, surface: pygame.Surface) -> None:
        for tile in self.deco_tiles:
            tile.render(surface, 0, 40)

        pygame.draw.rect(
            self.screen_alpha_surface,
            (10, 8, 16, 190),
            pygame.Rect(0, 0, settings.VIRTUAL_WIDTH, settings.VIRTUAL_HEIGHT),
        )
        surface.blit(self.screen_alpha_surface, (0, 0))

        render_text(
            surface,
            "TRANSMUTACION",
            settings.FONTS["huge"],
            settings.VIRTUAL_WIDTH // 2,
            settings.VIRTUAL_HEIGHT // 2 - 100,
            (214, 64, 64),
            center=True,
            shadowed=True,
        )
        render_text(
            surface,
            "ARCANA",
            settings.FONTS["large"],
            settings.VIRTUAL_WIDTH // 2,
            settings.VIRTUAL_HEIGHT // 2 - 50,
            (150, 72, 196),
            center=True,
            shadowed=True,
        )
        render_text(
            surface,
            "Un juego de match-3",
            settings.FONTS["small"],
            settings.VIRTUAL_WIDTH // 2,
            settings.VIRTUAL_HEIGHT // 2 - 16,
            (200, 200, 210),
            center=True,
            shadowed=True,
        )

        start_color = (99, 255, 155) if self.current_menu_item == 1 else (90, 90, 100)
        quit_color = (99, 255, 155) if self.current_menu_item == 2 else (90, 90, 100)

        render_text(
            surface,
            "Comenzar",
            settings.FONTS["medium"],
            settings.VIRTUAL_WIDTH // 2,
            settings.VIRTUAL_HEIGHT // 2 + 30,
            start_color,
            center=True,
            shadowed=True,
        )
        render_text(
            surface,
            "Salir",
            settings.FONTS["medium"],
            settings.VIRTUAL_WIDTH // 2,
            settings.VIRTUAL_HEIGHT // 2 + 60,
            quit_color,
            center=True,
            shadowed=True,
        )

        pygame.draw.rect(
            self.screen_alpha_surface,
            (255, 255, 255, self.alpha_transition),
            pygame.Rect(0, 0, settings.VIRTUAL_WIDTH, settings.VIRTUAL_HEIGHT),
        )
        surface.blit(self.screen_alpha_surface, (0, 0))

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if not self.active:
            return

        if input_id in ("up", "down") and input_data.pressed:
            self.current_menu_item = 1 if self.current_menu_item == 2 else 2
        elif input_id == "enter" and input_data.pressed:
            if self.current_menu_item == 1:
                self.active = False
                Timer.tween(
                    0.5,
                    [(self, {"alpha_transition": 255})],
                    on_finish=lambda: self.state_machine.change("play"),
                )
            else:
                self.game.quit()
