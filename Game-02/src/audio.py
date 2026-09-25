"""
audio.py

Efecto de fusión (check.mp3) y música de fondo (Bucle_music.mp3) de 2048.
"""
from __future__ import annotations

from typing import Dict, Optional

import pygame

import settings

# Audio (assets/check.mp3): se reproduce al fusionar dos fichas y al
# confirmar en la portada. Se carga una sola vez (cacheado) igual que la
# imagen de portada y el fondo.
# ---------------------------------------------------------------------------
_SOUND_CACHE: Dict[str, Optional[pygame.mixer.Sound]] = {}


def check_sound() -> Optional[pygame.mixer.Sound]:
    """
    Carga (una sola vez) el efecto 'check'. Si el mezclador de audio no
    está disponible en el entorno actual (por ejemplo, sin dispositivo de
    sonido en un servidor sin cabeza), se atrapa el error y se devuelve
    None: el juego sigue funcionando en silencio en vez de fallar.
    """
    if "check" not in _SOUND_CACHE:
        try:
            _SOUND_CACHE["check"] = pygame.mixer.Sound(str(settings.CHECK_SOUND_PATH))
        except pygame.error:
            _SOUND_CACHE["check"] = None

    return _SOUND_CACHE["check"]


# ---------------------------------------------------------------------------
# Música de fondo (assets/Bucle_music.mp3): suena en bucle infinito durante
# la partida. A diferencia de check.mp3 (un efecto corto que se carga
# entero en memoria con pygame.mixer.Sound), esta es una pista larga
# pensada para sonar de fondo, así que se transmite con pygame.mixer.music
# -sólo puede haber una activa a la vez, que es justo lo que se necesita
# para música de fondo- en vez de cargarla completa en RAM.
# ---------------------------------------------------------------------------


def start_game_music() -> None:
    """
    Carga y reproduce Bucle_music.mp3 en bucle infinito (loops=-1). Se
    llama cada vez que arranca una partida (PlayState.enter), incluido un
    reinicio, así que la música también vuelve a empezar desde el inicio
    en cada reinicio. Si no hay dispositivo de audio disponible, se
    atrapa el error y la partida sigue en silencio.
    """
    try:
        pygame.mixer.music.load(str(settings.GAME_MUSIC_PATH))
        pygame.mixer.music.play(loops=-1)
    except pygame.error:
        pass


def stop_music() -> None:
    """Corta la música de fondo (se llama al salir de PlayState: game over)."""
    try:
        pygame.mixer.music.stop()
    except pygame.error:
        pass
