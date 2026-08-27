"""
Modulo C - Combate RPG.

Character: un personaje de combate (jugador o enemigo). Su sprite es
pixel-art original, autogenerado (ver tools/generate_character_sprites.py,
misma tecnica que tools/generate_portraits.py) y guardado como una hoja
de 5 frames en assets/graphics/characters/ -- no hay ninguna imagen de
stock, IP de terceros ni asset "ripeado" involucrado. Character solo
recorta esos 5 frames y los anima:
    idle_a/idle_b      -- loop de respiracion (bob en la cabeza/postura)
    attack_a/attack_b  -- golpe en dos tiempos: impulso y puñetazo/impacto
    hurt               -- pose de reaccion (guardia baja, cabeza atras),
                           mostrada junto con el parpadeo rojo al recibir dano
"""

from typing import Callable, Optional, Tuple

import pygame

import settings
from gale.timer import Timer

_SPRITES_DIR = settings.BASE_DIR / "assets" / "graphics" / "characters"
_FRAME_NAMES = ("idle_a", "idle_b", "attack_a", "attack_b", "hurt")
_IDLE_BOB_INTERVAL = 0.45


def _load_frames(is_player: bool) -> dict:
    path = _SPRITES_DIR / ("player.png" if is_player else "enemy.png")
    sheet = pygame.image.load(path).convert_alpha()
    size = settings.CHARACTER_SPRITE_SIZE
    frames = {}
    for index, name in enumerate(_FRAME_NAMES):
        rect = pygame.Rect(index * size, 0, size, size)
        frames[name] = sheet.subsurface(rect).copy()
    return frames


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

        frames = _load_frames(is_player)
        self._sprites = {
            "idle": [frames["idle_a"], frames["idle_b"]],
            "atacando": [frames["attack_a"], frames["attack_b"]],
            "danado": frames["hurt"],
        }
        self._idle_frame = 0
        self.sprite = self._sprites["idle"][0]
        Timer.every(_IDLE_BOB_INTERVAL, self._advance_idle)

    # -- Animacion ------------------------------------------------------

    def _advance_idle(self) -> None:
        self._idle_frame = 1 - self._idle_frame
        if self.state == "idle":
            self.sprite = self._sprites["idle"][self._idle_frame]

    def play_attack(self, on_finish: Optional[Callable[[], None]] = None) -> None:
        self.state = "atacando"
        self.sprite = self._sprites["atacando"][0]  # impulso

        def _impact():
            self.sprite = self._sprites["atacando"][1]  # golpe
            if on_finish:
                on_finish()

        def _recover():
            self.state = "idle"
            self.sprite = self._sprites["idle"][self._idle_frame]

        Timer.after(0.15, _impact)
        Timer.after(0.35, _recover)

    def play_hurt(self) -> None:
        self.state = "danado"
        self.sprite = self._sprites["danado"]

        def _toggle():
            self.hurt_flash = not self.hurt_flash

        def _stop():
            self.hurt_flash = False
            self.state = "idle"
            self.sprite = self._sprites["idle"][self._idle_frame]

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
