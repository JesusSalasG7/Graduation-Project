"""
This file contains the class BeginGameState: the transition screen
shown before each battle. It (re)builds the board and, on a fresh run,
the player's Combatant/EssencePool; on a level-up it receives them from
BattleState so HP and essence persist across the campaign.
"""

from typing import Any, Dict

import pygame

from gale.state import BaseState
from gale.text import render_text
from gale.timer import Timer

import settings
from src.board.board import Board
from src.combat.combat_controller import CombatController
from src.combat.enemies import make_enemy
from src.rpg.essence import EssencePool
from src.rpg.stats import Combatant


class BeginGameState(BaseState):
    def enter(self, **enter_params: Dict[str, Any]) -> None:
        self.transition_alpha = 255
        self.label_y = -64

        self.level = enter_params.get("level", 1)
        self.player = enter_params.get("player") or Combatant(
            "Alquimista", settings.PLAYER_MAX_HP
        )
        self.essence = enter_params.get("essence") or EssencePool()

        self.enemy, self.enemy_color, self.enemy_sprite = make_enemy(self.level)
        self.board = Board(settings.BOARD_X, settings.BOARD_Y)
        self.controller = CombatController(self.player, self.enemy, self.essence)

        self.screen_alpha_surface = pygame.Surface(
            (settings.VIRTUAL_WIDTH, settings.VIRTUAL_HEIGHT), pygame.SRCALPHA
        )

        Timer.tween(
            0.6,
            [(self, {"transition_alpha": 0})],
            on_finish=lambda: Timer.tween(
                0.25,
                [(self, {"label_y": settings.VIRTUAL_HEIGHT // 2 - 20})],
                on_finish=lambda: Timer.after(
                    1.1,
                    lambda: Timer.tween(
                        0.25,
                        [(self, {"label_y": settings.VIRTUAL_HEIGHT + 30})],
                        on_finish=lambda: self.state_machine.change(
                            "battle",
                            level=self.level,
                            board=self.board,
                            player=self.player,
                            essence=self.essence,
                            enemy=self.enemy,
                            enemy_color=self.enemy_color,
                            enemy_sprite=self.enemy_sprite,
                            controller=self.controller,
                        ),
                    ),
                ),
            ),
        )

    def render(self, surface: pygame.Surface) -> None:
        self.board.render(surface)

        sprite = pygame.transform.scale(self.enemy_sprite, (96, 96))
        sprite_rect = sprite.get_rect(
            center=(settings.VIRTUAL_WIDTH // 2, self.label_y - 60)
        )
        surface.blit(sprite, sprite_rect)

        render_text(
            surface,
            f"Combate {self.level}",
            settings.FONTS["large"],
            settings.VIRTUAL_WIDTH // 2,
            self.label_y,
            (235, 235, 240),
            center=True,
            shadowed=True,
        )
        render_text(
            surface,
            self.enemy.name,
            settings.FONTS["medium"],
            settings.VIRTUAL_WIDTH // 2,
            self.label_y + 34,
            self.enemy_color,
            center=True,
            shadowed=True,
        )

        pygame.draw.rect(
            self.screen_alpha_surface,
            (10, 8, 16, self.transition_alpha),
            pygame.Rect(0, 0, settings.VIRTUAL_WIDTH, settings.VIRTUAL_HEIGHT),
        )
        surface.blit(self.screen_alpha_surface, (0, 0))
