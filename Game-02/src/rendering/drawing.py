"""
drawing.py

Helpers de dibujo compartidos por los estados de 2048: posición de las
celdas, fondo espacial, tarjeta central, texto con resplandor y portada.
"""
from __future__ import annotations

import random
from typing import Dict, Tuple

import pygame

import settings
from src.rendering.theme import (
    BOARD_LEFT,
    BOARD_TOP,
    CELL_GAP,
    CELL_SIZE,
    COLOR_BACKGROUND_BOTTOM,
    COLOR_BACKGROUND_TOP,
    COLOR_GLOW_BLUE,
    COLOR_GLOW_MAGENTA,
    COLOR_PANEL,
    COLOR_PANEL_BORDER,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)


def ease_out_cubic(t: float) -> float:
    """Desaceleración suave al llegar al destino (en vez de movimiento lineal robótico)."""
    return 1.0 - (1.0 - t) ** 3


def cell_rect(row: float, col: float) -> pygame.Rect:
    """Acepta fila/col fraccionarios: son los que usa la animación de deslizamiento."""
    x = BOARD_LEFT + CELL_GAP + col * (CELL_SIZE + CELL_GAP)
    y = BOARD_TOP + CELL_GAP + row * (CELL_SIZE + CELL_GAP)
    return pygame.Rect(round(x), round(y), CELL_SIZE, CELL_SIZE)


# ---------------------------------------------------------------------------
# Fondo "espacial" (degradado + resplandores + estrellas) y tarjeta central.
#
# Generar esto píxel a píxel sería lento si se hiciera en cada frame, así
# que se arma UNA sola vez (un degradado vertical de ~850 líneas más un
# puñado de círculos para los halos y las estrellas) y se cachea en
# `_BACKGROUND_CACHE`, indexado por tamaño de ventana. `PlayState.enter()` se
# vuelve a llamar cada vez que el jugador reinicia (tecla R), así que sin
# este caché se repetiría el costo de generar el fondo en cada reinicio.
# ---------------------------------------------------------------------------
_BACKGROUND_CACHE: Dict[Tuple[int, int], pygame.Surface] = {}


def _blend_color(color_a: Tuple[int, int, int], color_b: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
    """Interpola linealmente entre dos colores RGB según t en [0, 1]."""
    return tuple(int(color_a[i] + (color_b[i] - color_a[i]) * t) for i in range(3))


def _draw_glow(
    base: pygame.Surface, center: Tuple[int, int], max_radius: float, color: Tuple[int, int, int]
) -> None:
    """
    Simula un halo de luz suave: dibuja muchos círculos concéntricos, cada
    uno casi transparente, sobre una capa auxiliar con canal alfa, y la
    mezcla con el fondo en modo aditivo (suma de color, no reemplazo) para
    que el resultado se vea como un brillo y no como un círculo sólido.
    """
    layers = 24
    overlay = pygame.Surface(base.get_size(), pygame.SRCALPHA)
    for i in range(layers, 0, -1):
        radius = int(max_radius * i / layers)
        alpha = int(2 + (i / layers) * 9)  # muy sutil: capas finas que se van sumando
        pygame.draw.circle(overlay, (*color, alpha), center, radius)
    base.blit(overlay, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)


def space_background(width: int, height: int) -> pygame.Surface:
    """Devuelve (generándolo una sola vez y reutilizándolo después) el fondo estrellado."""
    key = (width, height)
    if key in _BACKGROUND_CACHE:
        return _BACKGROUND_CACHE[key]

    surface = pygame.Surface((width, height))

    # Degradado vertical azul marino -> púrpura (barato: una línea por fila,
    # no un cálculo por píxel).
    for y in range(height):
        t = y / max(1, height - 1)
        color = _blend_color(COLOR_BACKGROUND_TOP, COLOR_BACKGROUND_BOTTOM, t)
        pygame.draw.line(surface, color, (0, y), (width, y))

    # Halos de color en las esquinas opuestas, para sugerir profundidad
    # diagonal sin tener que calcular un degradado diagonal real.
    _draw_glow(surface, (0, 0), max(width, height) * 0.55, COLOR_GLOW_BLUE)
    _draw_glow(surface, (width, height), max(width, height) * 0.6, COLOR_GLOW_MAGENTA)

    # Estrellas decorativas: semilla fija para que el cielo generado sea
    # siempre el mismo (reproducible), no distinto en cada partida.
    generator = random.Random(20480)
    for _ in range(70):
        x = generator.randint(0, width - 1)
        y = generator.randint(0, height - 1)
        radius = generator.choice((1, 1, 1, 2))
        brightness = generator.randint(90, 200)
        pygame.draw.circle(surface, (brightness, brightness, min(255, brightness + 35)), (x, y), radius)

    _BACKGROUND_CACHE[key] = surface
    return surface


def draw_panel(surface: pygame.Surface) -> None:
    """Tarjeta oscura con borde brillante que enmarca todo el juego, sobre el fondo estrellado."""
    margin = 14
    radius = 28
    panel_rect = pygame.Rect(margin, margin, WINDOW_WIDTH - 2 * margin, WINDOW_HEIGHT - 2 * margin)

    pygame.draw.rect(surface, COLOR_PANEL, panel_rect, border_radius=radius)

    # Resplandor del borde: tres anillos concéntricos hacia afuera del
    # panel, cada vez más grandes y más tenues (mismo truco que el halo de
    # fondo, pero como simples trazos en vez de círculos rellenos).
    rings = ((2, 1.0), (5, 0.55), (9, 0.3))
    for offset, intensity in rings:
        ring_color = tuple(int(c * intensity) for c in COLOR_PANEL_BORDER)
        border_rect = panel_rect.inflate(offset * 2, offset * 2)
        pygame.draw.rect(surface, ring_color, border_rect, width=2, border_radius=radius + offset)


def draw_text_with_glow(
    surface: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    main_color: Tuple[int, int, int],
    glow_color: Tuple[int, int, int],
    corner_position: Tuple[int, int],
) -> None:
    """
    Efecto de "glow" barato: primero se dibuja el mismo texto en un color
    cálido varias veces, desplazado un par de píxeles en las 8 direcciones
    alrededor de la posición final, formando un halo/contorno grueso; luego
    se dibuja el texto real, en el color principal, exactamente encima.
    """
    glow_text = font.render(text, True, glow_color)
    for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, 2), (-2, 2), (2, -2)):
        surface.blit(glow_text, (corner_position[0] + dx, corner_position[1] + dy))

    main_text = font.render(text, True, main_color)
    surface.blit(main_text, corner_position)


# ---------------------------------------------------------------------------
# Portada (Cover.png): se carga y se reescala una sola vez -igual que el
# fondo estrellado- y se cachea por tamaño de ventana, para no tocar disco
# ni reescalar de nuevo si el jugador vuelve a ver la portada.
# ---------------------------------------------------------------------------
_COVER_CACHE: Dict[Tuple[int, int], Tuple[pygame.Surface, pygame.Rect]] = {}


def cover_image(window_width: int, window_height: int) -> Tuple[pygame.Surface, pygame.Rect]:
    key = (window_width, window_height)
    if key in _COVER_CACHE:
        return _COVER_CACHE[key]

    original = pygame.image.load(str(settings.COVER_PATH)).convert_alpha()

    # Se escala preservando la proporción original, para que quepa entera
    # dentro de la ventana sin deformarse (el lado que sobre queda como
    # margen, centrado).
    scale = min(window_width / original.get_width(), window_height / original.get_height())
    new_width = round(original.get_width() * scale)
    new_height = round(original.get_height() * scale)
    image = pygame.transform.smoothscale(original, (new_width, new_height))
    rect = image.get_rect(center=(window_width // 2, window_height // 2))

    _COVER_CACHE[key] = (image, rect)
    return _COVER_CACHE[key]
