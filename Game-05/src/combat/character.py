"""
Modulo C - Combate RPG.

Character: un personaje de combate (jugador o enemigo). Su sprite es
pixel-art generado con pygame.draw sobre una superficie chica (16x16)
y despues escalado sin suavizado -- no se cargan imagenes externas.
Solo tiene 3 estados: idle, atacando (con su propio frame) y danado
(parpadeo rojo sobre el frame idle).
"""

from typing import Callable, Optional, Tuple

import pygame

import settings
from gale.timer import Timer


class Character:
    def __init__(
        self, name: str, max_hp: int, anchor: Tuple[int, int], is_player: bool
    ) -> None:
        self.name = name
        self.max_hp = max_hp
        self.hp = max_hp
        self.anchor = anchor
        self.is_player = is_player

        self.state = "idle"
        self.hurt_flash = False
        self.stunned = False
        # Multiplicador para SU proximo ataque -- Tierra/Hielo del
        # rival lo dejan en 0.5 ("lo ralentizan") hasta que ataque.
        self.next_attack_multiplier = 1.0

        self._palette = (
            {"piel": (235, 200, 160), "ropa": (70, 110, 200), "borde": (20, 18, 30)}
            if is_player
            else {"piel": (150, 200, 120), "ropa": (170, 60, 60), "borde": (20, 18, 30)}
        )
        self._sprites = {
            "idle": self._build_sprite(attacking=False),
            "atacando": self._build_sprite(attacking=True),
        }
        self.sprite = self._sprites["idle"]

    # -- Pixel-art ----------------------------------------------------

    def _build_sprite(self, attacking: bool) -> pygame.Surface:
        size = settings.CHARACTER_SPRITE_BASE_SIZE
        base = pygame.Surface((size, size), pygame.SRCALPHA)
        p = self._palette
        # El enemigo mira hacia la izquierda (hacia el jugador).
        facing = 1 if self.is_player else -1

        pygame.draw.rect(base, p["ropa"], pygame.Rect(4, 7, 8, 7))
        pygame.draw.rect(base, p["piel"], pygame.Rect(5, 2, 6, 6))
        pygame.draw.rect(base, p["borde"], pygame.Rect(5, 2, 6, 6), width=1)
        pygame.draw.rect(base, p["ropa"], pygame.Rect(5, 14, 2, 2))
        pygame.draw.rect(base, p["ropa"], pygame.Rect(9, 14, 2, 2))

        # Brazo: pegado al torso en idle, extendido hacia el rival
        # (2px mas lejos) en la pose de ataque.
        reach = 2 if attacking else 0
        arm_x = 11 + reach if facing > 0 else 3 - reach
        pygame.draw.rect(base, p["piel"], pygame.Rect(arm_x, 8, 2, 4))

        return pygame.transform.scale(base, (settings.CHARACTER_SPRITE_SIZE,) * 2)

    # -- Animacion ------------------------------------------------------

    def play_attack(self, on_finish: Optional[Callable[[], None]] = None) -> None:
        self.state = "atacando"
        self.sprite = self._sprites["atacando"]

        def _impact():
            if on_finish:
                on_finish()

        def _recover():
            self.state = "idle"
            self.sprite = self._sprites["idle"]

        Timer.after(0.15, _impact)
        Timer.after(0.35, _recover)

    def play_hurt(self) -> None:
        self.state = "danado"

        def _toggle():
            self.hurt_flash = not self.hurt_flash

        def _stop():
            self.hurt_flash = False
            self.state = "idle"

        Timer.every(0.08, _toggle, limit=4, on_finish=_stop)

    # -- HP -------------------------------------------------------------

    def take_damage(self, amount: int) -> None:
        self.hp = max(0, self.hp - amount)
        self.play_hurt()

    def heal(self, amount: int) -> None:
        self.hp = min(self.max_hp, self.hp + amount)

    # -- Render -----------------------------------------------------------

    def render(self, surface: pygame.Surface) -> None:
        x, y = self.anchor
        rect = self.sprite.get_rect(center=(x, y))
        surface.blit(self.sprite, rect)

        if self.hurt_flash:
            overlay = pygame.Surface(self.sprite.get_size(), pygame.SRCALPHA)
            overlay.fill((255, 30, 30, 120))
            surface.blit(overlay, rect)

        self._render_hp_bar(surface, x, y - settings.HP_BAR_OFFSET_Y)

    def _render_hp_bar(self, surface: pygame.Surface, x: int, y: int) -> None:
        bar_rect = pygame.Rect(0, 0, settings.HP_BAR_WIDTH, settings.HP_BAR_HEIGHT)
        bar_rect.center = (x, y)

        ratio = self.hp / self.max_hp if self.max_hp else 0
        if ratio > 0.5:
            fill_color = (90, 210, 110)
        elif ratio > 0.25:
            fill_color = (230, 190, 60)
        else:
            fill_color = (220, 70, 70)

        fill_rect = bar_rect.copy()
        fill_rect.width = round(bar_rect.width * ratio)

        pygame.draw.rect(surface, (40, 40, 48), bar_rect)
        pygame.draw.rect(surface, fill_color, fill_rect)
        pygame.draw.rect(surface, (12, 10, 16), bar_rect, width=1)
