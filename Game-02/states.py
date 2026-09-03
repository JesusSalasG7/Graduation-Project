"""
states.py

Estados de la Máquina de Estados de Gale para 2048:
  - PortadaState: pantalla de inicio con la imagen de portada (Cover.png).
  - PlayState: tablero jugable, entrada de flechas, marcador.
  - GameOverState: pantalla final (victoria o derrota) con reinicio.
"""
from __future__ import annotations

import math
import random
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pygame

from gale.state import BaseState

import settings
from logic2048 import TAMANO, MovimientoFicha, Tablero

# ---------------------------------------------------------------------------
# Geometría de la interfaz (superficie virtual, ver settings.py)
# ---------------------------------------------------------------------------
WINDOW_WIDTH = settings.WINDOW_WIDTH
WINDOW_HEIGHT = settings.WINDOW_HEIGHT

BOARD_LEFT = 30
BOARD_TOP = 150
CELL_SIZE = 140
CELL_GAP = 16
BOARD_SIZE = TAMANO * CELL_SIZE + (TAMANO + 1) * CELL_GAP  # 640

# ---------------------------------------------------------------------------
# Paleta de colores "neón espacial", extraída con muestreo de píxeles de
# referencia.jpeg (color picker programático sobre la imagen, no a ojo).
# ---------------------------------------------------------------------------
# Fondo: degradado diagonal azul marino -> púrpura, con resplandores en las
# esquinas y una tarjeta oscura con borde brillante conteniendo el juego.
COLOR_FONDO_ARRIBA = (13, 20, 48)       # esquina superior (azul marino)
COLOR_FONDO_ABAJO = (46, 12, 46)        # esquina inferior (púrpura oscuro)
COLOR_RESPLANDOR_AZUL = (60, 110, 230)  # halo esquina superior-izquierda
COLOR_RESPLANDOR_MAGENTA = (200, 40, 150)  # halo esquina inferior-derecha

COLOR_PANEL = (19, 23, 46)              # tarjeta central donde vive el juego
COLOR_PANEL_BORDE = (100, 140, 255)     # color base del resplandor del borde

COLOR_TABLERO = (13, 16, 32)            # marco del tablero (más oscuro que las celdas)
COLOR_TEXTO_PRINCIPAL = (240, 236, 227)  # texto principal: blanco cálido
COLOR_TEXTO_TENUE = (135, 143, 173)      # texto secundario: gris azulado
COLOR_GLOW_TITULO = (245, 190, 90)       # resplandor dorado detrás del título

COLOR_TEXTO_OSCURO = (55, 60, 72)      # texto de fichas 2 y 4 (fondos claros)
COLOR_TEXTO_CLARO = (250, 248, 244)    # texto de fichas >= 8 (fondos saturados)

COLOR_VICTORIA = (255, 209, 102)  # dorado
COLOR_DERROTA = (255, 107, 107)   # rojo/rosa neón

COLORES_FICHA = {
    0: (44, 50, 68),      # celda vacía
    2: (196, 201, 204),   # gris plateado
    4: (219, 197, 160),   # beige/tostado
    8: (236, 135, 47),    # naranja
    16: (209, 95, 22),    # naranja quemado
    32: (246, 68, 54),    # rojo
    64: (177, 47, 195),   # púrpura
    128: (242, 200, 4),   # dorado
    256: (255, 221, 0),   # amarillo neón
    512: (0, 217, 219),   # cian
    1024: (6, 119, 213),  # azul
    2048: (233, 30, 140), # magenta neón
}
COLOR_FICHA_EXTRA = (18, 0, 26)  # fichas > 2048, violeta casi negro

# Mapea el identificador de acción registrado en InputHandler (main.py) a
# la dirección que entiende Tablero.mover().
DIRECCIONES_POR_ACCION = {
    "mover_izquierda": "IZQUIERDA",
    "mover_derecha": "DERECHA",
    "mover_arriba": "ARRIBA",
    "mover_abajo": "ABAJO",
}

# ---------------------------------------------------------------------------
# Animación: duración de cada fase de un movimiento, en segundos.
#   1) "deslizando":  las fichas existentes viajan de su celda de origen
#                     a su celda de destino (incluidas las que se
#                     fusionan, que convergen en la misma celda).
#   2) "apareciendo": el tablero ya muestra los valores finales; las
#                     celdas resultado de una fusión y la ficha nueva
#                     hacen un pequeño "pop" de escala para que se noten.
# Mientras cualquiera de las dos fases está activa se ignoran nuevas
# entradas de movimiento, para no encimar animaciones.
# ---------------------------------------------------------------------------
DURACION_DESLIZAMIENTO = 0.13
DURACION_APARICION = 0.09


def _ease_out_cubic(t: float) -> float:
    """Desaceleración suave al llegar al destino (en vez de movimiento lineal robótico)."""
    return 1.0 - (1.0 - t) ** 3


def _rect_celda(fila: float, col: float) -> pygame.Rect:
    """Acepta fila/col fraccionarios: son los que usa la animación de deslizamiento."""
    x = BOARD_LEFT + CELL_GAP + col * (CELL_SIZE + CELL_GAP)
    y = BOARD_TOP + CELL_GAP + fila * (CELL_SIZE + CELL_GAP)
    return pygame.Rect(round(x), round(y), CELL_SIZE, CELL_SIZE)


# ---------------------------------------------------------------------------
# Fondo "espacial" (degradado + resplandores + estrellas) y tarjeta central.
#
# Generar esto píxel a píxel sería lento si se hiciera en cada frame, así
# que se arma UNA sola vez (un degradado vertical de ~850 líneas más un
# puñado de círculos para los halos y las estrellas) y se cachea en
# `_CACHE_FONDO`, indexado por tamaño de ventana. `PlayState.enter()` se
# vuelve a llamar cada vez que el jugador reinicia (tecla R), así que sin
# este caché se repetiría el costo de generar el fondo en cada reinicio.
# ---------------------------------------------------------------------------
_CACHE_FONDO: Dict[Tuple[int, int], pygame.Surface] = {}


def _mezclar_color(color_a: Tuple[int, int, int], color_b: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
    """Interpola linealmente entre dos colores RGB según t en [0, 1]."""
    return tuple(int(color_a[i] + (color_b[i] - color_a[i]) * t) for i in range(3))


def _dibujar_resplandor(
    base: pygame.Surface, centro: Tuple[int, int], radio_maximo: float, color: Tuple[int, int, int]
) -> None:
    """
    Simula un halo de luz suave: dibuja muchos círculos concéntricos, cada
    uno casi transparente, sobre una capa auxiliar con canal alfa, y la
    mezcla con el fondo en modo aditivo (suma de color, no reemplazo) para
    que el resultado se vea como un brillo y no como un círculo sólido.
    """
    capas = 24
    overlay = pygame.Surface(base.get_size(), pygame.SRCALPHA)
    for i in range(capas, 0, -1):
        radio = int(radio_maximo * i / capas)
        alpha = int(2 + (i / capas) * 9)  # muy sutil: capas finas que se van sumando
        pygame.draw.circle(overlay, (*color, alpha), centro, radio)
    base.blit(overlay, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)


def _fondo_espacial(ancho: int, alto: int) -> pygame.Surface:
    """Devuelve (generándolo una sola vez y reutilizándolo después) el fondo estrellado."""
    clave = (ancho, alto)
    if clave in _CACHE_FONDO:
        return _CACHE_FONDO[clave]

    superficie = pygame.Surface((ancho, alto))

    # Degradado vertical azul marino -> púrpura (barato: una línea por fila,
    # no un cálculo por píxel).
    for y in range(alto):
        t = y / max(1, alto - 1)
        color = _mezclar_color(COLOR_FONDO_ARRIBA, COLOR_FONDO_ABAJO, t)
        pygame.draw.line(superficie, color, (0, y), (ancho, y))

    # Halos de color en las esquinas opuestas, para sugerir profundidad
    # diagonal sin tener que calcular un degradado diagonal real.
    _dibujar_resplandor(superficie, (0, 0), max(ancho, alto) * 0.55, COLOR_RESPLANDOR_AZUL)
    _dibujar_resplandor(superficie, (ancho, alto), max(ancho, alto) * 0.6, COLOR_RESPLANDOR_MAGENTA)

    # Estrellas decorativas: semilla fija para que el cielo generado sea
    # siempre el mismo (reproducible), no distinto en cada partida.
    generador = random.Random(20480)
    for _ in range(70):
        x = generador.randint(0, ancho - 1)
        y = generador.randint(0, alto - 1)
        radio = generador.choice((1, 1, 1, 2))
        brillo = generador.randint(90, 200)
        pygame.draw.circle(superficie, (brillo, brillo, min(255, brillo + 35)), (x, y), radio)

    _CACHE_FONDO[clave] = superficie
    return superficie


def _dibujar_panel(surface: pygame.Surface) -> None:
    """Tarjeta oscura con borde brillante que enmarca todo el juego, sobre el fondo estrellado."""
    margen = 14
    radio = 28
    panel_rect = pygame.Rect(margen, margen, WINDOW_WIDTH - 2 * margen, WINDOW_HEIGHT - 2 * margen)

    pygame.draw.rect(surface, COLOR_PANEL, panel_rect, border_radius=radio)

    # Resplandor del borde: tres anillos concéntricos hacia afuera del
    # panel, cada vez más grandes y más tenues (mismo truco que el halo de
    # fondo, pero como simples trazos en vez de círculos rellenos).
    anillos = ((2, 1.0), (5, 0.55), (9, 0.3))
    for offset, intensidad in anillos:
        color_anillo = tuple(int(c * intensidad) for c in COLOR_PANEL_BORDE)
        borde_rect = panel_rect.inflate(offset * 2, offset * 2)
        pygame.draw.rect(surface, color_anillo, borde_rect, width=2, border_radius=radio + offset)


def _dibujar_texto_con_resplandor(
    surface: pygame.Surface,
    fuente: pygame.font.Font,
    texto: str,
    color_principal: Tuple[int, int, int],
    color_resplandor: Tuple[int, int, int],
    posicion_esquina: Tuple[int, int],
) -> None:
    """
    Efecto de "glow" barato: primero se dibuja el mismo texto en un color
    cálido varias veces, desplazado un par de píxeles en las 8 direcciones
    alrededor de la posición final, formando un halo/contorno grueso; luego
    se dibuja el texto real, en el color principal, exactamente encima.
    """
    texto_resplandor = fuente.render(texto, True, color_resplandor)
    for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, 2), (-2, 2), (2, -2)):
        surface.blit(texto_resplandor, (posicion_esquina[0] + dx, posicion_esquina[1] + dy))

    texto_principal = fuente.render(texto, True, color_principal)
    surface.blit(texto_principal, posicion_esquina)


# ---------------------------------------------------------------------------
# Portada (Cover.png): se carga y se reescala una sola vez -igual que el
# fondo estrellado- y se cachea por tamaño de ventana, para no tocar disco
# ni reescalar de nuevo si el jugador vuelve a ver la portada.
# ---------------------------------------------------------------------------
_RUTA_COVER = Path(__file__).resolve().parent / "assets" / "Cover.png"
_CACHE_PORTADA: Dict[Tuple[int, int], Tuple[pygame.Surface, pygame.Rect]] = {}


def _imagen_portada(ancho_ventana: int, alto_ventana: int) -> Tuple[pygame.Surface, pygame.Rect]:
    clave = (ancho_ventana, alto_ventana)
    if clave in _CACHE_PORTADA:
        return _CACHE_PORTADA[clave]

    original = pygame.image.load(str(_RUTA_COVER)).convert_alpha()

    # Se escala preservando la proporción original, para que quepa entera
    # dentro de la ventana sin deformarse (el lado que sobre queda como
    # margen, centrado).
    escala = min(ancho_ventana / original.get_width(), alto_ventana / original.get_height())
    nuevo_ancho = round(original.get_width() * escala)
    nuevo_alto = round(original.get_height() * escala)
    imagen = pygame.transform.smoothscale(original, (nuevo_ancho, nuevo_alto))
    rect = imagen.get_rect(center=(ancho_ventana // 2, alto_ventana // 2))

    _CACHE_PORTADA[clave] = (imagen, rect)
    return _CACHE_PORTADA[clave]


# ---------------------------------------------------------------------------
# Audio (assets/check.mp3): se reproduce al fusionar dos fichas y al
# confirmar en la portada. Se carga una sola vez (cacheado) igual que la
# imagen de portada y el fondo.
# ---------------------------------------------------------------------------
_RUTA_SONIDO_CHECK = Path(__file__).resolve().parent / "assets" / "check.mp3"
_CACHE_SONIDOS: Dict[str, Optional[pygame.mixer.Sound]] = {}


def _sonido_check() -> Optional[pygame.mixer.Sound]:
    """
    Carga (una sola vez) el efecto 'check'. Si el mezclador de audio no
    está disponible en el entorno actual (por ejemplo, sin dispositivo de
    sonido en un servidor sin cabeza), se atrapa el error y se devuelve
    None: el juego sigue funcionando en silencio en vez de fallar.
    """
    if "check" not in _CACHE_SONIDOS:
        try:
            _CACHE_SONIDOS["check"] = pygame.mixer.Sound(str(_RUTA_SONIDO_CHECK))
        except pygame.error:
            _CACHE_SONIDOS["check"] = None

    return _CACHE_SONIDOS["check"]


# ---------------------------------------------------------------------------
# Música de fondo (assets/Bucle_music.mp3): suena en bucle infinito durante
# la partida. A diferencia de check.mp3 (un efecto corto que se carga
# entero en memoria con pygame.mixer.Sound), esta es una pista larga
# pensada para sonar de fondo, así que se transmite con pygame.mixer.music
# -sólo puede haber una activa a la vez, que es justo lo que se necesita
# para música de fondo- en vez de cargarla completa en RAM.
# ---------------------------------------------------------------------------
_RUTA_MUSICA_JUEGO = Path(__file__).resolve().parent / "assets" / "Bucle_music.mp3"


def _iniciar_musica_juego() -> None:
    """
    Carga y reproduce Bucle_music.mp3 en bucle infinito (loops=-1). Se
    llama cada vez que arranca una partida (PlayState.enter), incluido un
    reinicio, así que la música también vuelve a empezar desde el inicio
    en cada reinicio. Si no hay dispositivo de audio disponible, se
    atrapa el error y la partida sigue en silencio.
    """
    try:
        pygame.mixer.music.load(str(_RUTA_MUSICA_JUEGO))
        pygame.mixer.music.play(loops=-1)
    except pygame.error:
        pass


def _detener_musica() -> None:
    """Corta la música de fondo (se llama al salir de PlayState: game over)."""
    try:
        pygame.mixer.music.stop()
    except pygame.error:
        pass


class PortadaState(BaseState):
    """
    Pantalla de inicio: muestra Cover.png sobre el fondo espacial, con un
    mensaje parpadeante, hasta que el jugador presiona ENTER (ESC sigue
    saliendo del juego: Juego2048.on_input la intercepta antes de que
    llegue aquí). Es el primer estado que ve el jugador al arrancar.
    """

    ALTO_BARRA_PROMPT = 74

    def enter(self, *args, **kwargs) -> None:
        self.fuente_prompt = pygame.font.SysFont("arial", 24, bold=True)
        self.tiempo = 0.0
        self.imagen, self.rect_imagen = _imagen_portada(WINDOW_WIDTH, WINDOW_HEIGHT)

    def exit(self) -> None:
        pass

    def on_input(self, input_id: str, input_data) -> None:
        # Sólo ENTER (main.py la registra como "confirmar", tanto la tecla
        # principal como la del teclado numérico) arranca la partida; se
        # ignora cualquier otra tecla, incluidas las flechas.
        if input_id == "confirmar" and getattr(input_data, "pressed", False):
            sonido = _sonido_check()
            if sonido is not None:
                sonido.play()
            self.state_machine.change("jugar")

    def update(self, dt: float) -> None:
        self.tiempo += dt

    def render(self, surface: pygame.Surface) -> None:
        surface.blit(_fondo_espacial(*surface.get_size()), (0, 0))
        surface.blit(self.imagen, self.rect_imagen)

        # Barra semitransparente en la base, para que el texto se lea sin
        # importar qué haya justo debajo en la imagen de portada.
        barra = pygame.Surface((WINDOW_WIDTH, self.ALTO_BARRA_PROMPT), pygame.SRCALPHA)
        barra.fill((0, 0, 0, 150))
        surface.blit(barra, (0, WINDOW_HEIGHT - self.ALTO_BARRA_PROMPT))

        # Parpadeo suave (oscilación seno) en vez de fijo, para que llame
        # la atención como una invitación a jugar.
        alpha = int(160 + 95 * math.sin(self.tiempo * 3.0))
        texto = self.fuente_prompt.render(
            "PRESIONA ENTER PARA JUGAR", True, COLOR_TEXTO_PRINCIPAL
        )
        texto.set_alpha(max(0, min(255, alpha)))
        rect_texto = texto.get_rect(
            center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT - self.ALTO_BARRA_PROMPT // 2)
        )
        surface.blit(texto, rect_texto)


class PlayState(BaseState):
    """
    Estado jugable: tablero 4x4, entrada de flechas y marcador.

    La animación de un movimiento avanza por tres fases guardadas en
    `self.fase`:
      "quieto"      -> esperando entrada del jugador.
      "deslizando"  -> las fichas viajan de origen a destino.
      "apareciendo" -> ya se ven los valores finales; fusiones y ficha
                        nueva hacen un pequeño "pop" de escala.
    `Tablero.mover()` sigue siendo instantáneo (el tablero lógico queda
    resuelto de inmediato); lo único que se retrasa visualmente es el
    dibujo, interpolando entre la posición anterior y la nueva.
    """

    def enter(self, *args, **kwargs) -> None:
        self.tablero = Tablero()

        self.fuente_titulo = pygame.font.SysFont("arial", 48, bold=True)
        self.fuente_marcador = pygame.font.SysFont("arial", 28, bold=True)
        self.fuente_ficha_grande = pygame.font.SysFont("arial", 56, bold=True)
        self.fuente_ficha_media = pygame.font.SysFont("arial", 45, bold=True)
        self.fuente_ficha_chica = pygame.font.SysFont("arial", 34, bold=True)

        self.rect_tablero = pygame.Rect(BOARD_LEFT, BOARD_TOP, BOARD_SIZE, BOARD_SIZE)

        # Estado de la animación en curso (ver docstring de la clase).
        self.fase: str = "quieto"
        self.tiempo_fase: float = 0.0
        self.movimientos_actuales: list[MovimientoFicha] = []
        self.celdas_fusionadas: Set[Tuple[int, int]] = set()
        self.posicion_ficha_nueva: Tuple[int, int] | None = None

        # La música de la partida arranca aquí; también se reinicia desde
        # cero cada vez que "reiniciar" vuelve a llamar a este mismo
        # enter() (ver on_input más abajo).
        _iniciar_musica_juego()

    def exit(self) -> None:
        _detener_musica()

    # ------------------------------------------------------------------
    def _fuente_para(self, valor: int) -> pygame.font.Font:
        digitos = len(str(valor))
        if digitos <= 2:
            return self.fuente_ficha_grande
        if digitos == 3:
            return self.fuente_ficha_media
        return self.fuente_ficha_chica

    # ------------------------------------------------------------------
    # Entrada
    # ------------------------------------------------------------------
    def on_input(self, input_id: str, input_data) -> None:
        if not getattr(input_data, "pressed", False):
            return

        if input_id == "reiniciar":
            self.enter()
            return

        if self.fase != "quieto":
            # Se ignoran movimientos nuevos mientras el anterior todavía
            # se está animando, para no encimar deslizamientos.
            return

        direccion = DIRECCIONES_POR_ACCION.get(input_id)
        if direccion is None:
            return

        resultado = self.tablero.mover(direccion)
        if not resultado.hubo_cambio:
            return

        self.movimientos_actuales = resultado.movimientos
        self.posicion_ficha_nueva = resultado.posicion_ficha_nueva
        self.celdas_fusionadas = {m.destino for m in resultado.movimientos if m.fusiono}

        self.fase = "deslizando"
        self.tiempo_fase = 0.0

    # ------------------------------------------------------------------
    # Actualización de la animación
    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        if self.fase == "quieto":
            return

        self.tiempo_fase += dt

        if self.fase == "deslizando" and self.tiempo_fase >= DURACION_DESLIZAMIENTO:
            # El deslizamiento terminó: a partir de ahora se dibuja
            # directamente desde self.tablero.celdas (que ya tiene los
            # valores finales, incluida la ficha nueva) con el "pop".
            self.fase = "apareciendo"
            self.tiempo_fase = 0.0

            # Sonido de fusión: una reproducción por cada par de fichas que
            # se unió en este movimiento (celdas_fusionadas trae un
            # elemento por cada celda destino donde convergieron dos
            # fichas), justo cuando el deslizamiento termina y el "pop" de
            # la fusión empieza a verse.
            if self.celdas_fusionadas:
                sonido = _sonido_check()
                if sonido is not None:
                    for _ in self.celdas_fusionadas:
                        sonido.play()

        elif self.fase == "apareciendo" and self.tiempo_fase >= DURACION_APARICION:
            self.fase = "quieto"
            self.tiempo_fase = 0.0
            if self.tablero.gano or self.tablero.perdio:
                self.state_machine.change(
                    "gameover", victoria=self.tablero.gano, puntuacion=self.tablero.puntuacion
                )

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------
    def render(self, surface: pygame.Surface) -> None:
        surface.blit(_fondo_espacial(*surface.get_size()), (0, 0))
        _dibujar_panel(surface)
        self._dibujar_encabezado(surface)

        pygame.draw.rect(surface, COLOR_TABLERO, self.rect_tablero, border_radius=8)
        self._dibujar_celdas_vacias(surface)

        if self.fase == "deslizando":
            self._dibujar_fichas_deslizando(surface)
        else:
            self._dibujar_fichas_estaticas(surface)

    def _dibujar_encabezado(self, surface: pygame.Surface) -> None:
        _dibujar_texto_con_resplandor(
            surface, self.fuente_titulo, "2048", COLOR_TEXTO_PRINCIPAL, COLOR_GLOW_TITULO, (30, 18)
        )

        texto_score = self.fuente_marcador.render(
            f"Puntuación: {self.tablero.puntuacion}", True, COLOR_TEXTO_PRINCIPAL
        )
        rect_score = texto_score.get_rect(topright=(WINDOW_WIDTH - 30, 28))
        surface.blit(texto_score, rect_score)

        ayuda = pygame.font.SysFont("arial", 20).render(
            "Flechas: mover   R: reiniciar   ESC: salir", True, COLOR_TEXTO_TENUE
        )
        surface.blit(ayuda, (30, 84))

    def _dibujar_celdas_vacias(self, surface: pygame.Surface) -> None:
        """Fondo fijo de las 16 celdas, siempre visible debajo de las fichas animadas."""
        for fila in range(TAMANO):
            for col in range(TAMANO):
                pygame.draw.rect(surface, COLORES_FICHA[0], _rect_celda(fila, col), border_radius=6)

    def _dibujar_ficha_en_rect(
        self, surface: pygame.Surface, rect: pygame.Rect, valor: int, escala: float = 1.0
    ) -> None:
        color = COLORES_FICHA.get(valor, COLOR_FICHA_EXTRA)

        if escala < 1.0:
            ancho = max(1, int(rect.width * escala))
            alto = max(1, int(rect.height * escala))
            rect_dibujo = pygame.Rect(0, 0, ancho, alto)
            rect_dibujo.center = rect.center
        else:
            rect_dibujo = rect

        pygame.draw.rect(surface, color, rect_dibujo, border_radius=6)

        color_texto = COLOR_TEXTO_OSCURO if valor <= 4 else COLOR_TEXTO_CLARO
        fuente = self._fuente_para(valor)
        texto = fuente.render(str(valor), True, color_texto)
        surface.blit(texto, texto.get_rect(center=rect_dibujo.center))

    def _dibujar_fichas_deslizando(self, surface: pygame.Surface) -> None:
        """
        Fase 1: interpola cada MovimientoFicha entre su celda de origen y
        su celda de destino. Las fichas que se fusionan se dibujan al
        final (por encima) para que se vea con claridad cómo dos fichas
        del mismo valor convergen en una sola celda.
        """
        progreso = min(1.0, self.tiempo_fase / DURACION_DESLIZAMIENTO)
        progreso_suave = _ease_out_cubic(progreso)

        en_orden = sorted(self.movimientos_actuales, key=lambda m: m.fusiono)
        for movimiento in en_orden:
            fila_origen, col_origen = movimiento.origen
            fila_destino, col_destino = movimiento.destino

            fila = fila_origen + (fila_destino - fila_origen) * progreso_suave
            col = col_origen + (col_destino - col_origen) * progreso_suave

            self._dibujar_ficha_en_rect(surface, _rect_celda(fila, col), movimiento.valor_origen)

    def _dibujar_fichas_estaticas(self, surface: pygame.Surface) -> None:
        """
        Fase 2 ("apareciendo") y estado "quieto": dibuja directamente
        desde el tablero lógico (ya resuelto). Durante "apareciendo",
        las celdas de fusión y la ficha nueva crecen desde una escala
        menor hasta 1.0 para que su llegada se note.
        """
        progreso_pop = 1.0
        if self.fase == "apareciendo":
            progreso_pop = min(1.0, self.tiempo_fase / DURACION_APARICION)

        for fila in range(TAMANO):
            for col in range(TAMANO):
                valor = self.tablero.celdas[fila][col]
                if valor == 0:
                    continue

                escala = 1.0
                if self.fase == "apareciendo":
                    if (fila, col) in self.celdas_fusionadas:
                        escala = 0.7 + 0.3 * progreso_pop
                    elif self.posicion_ficha_nueva == (fila, col):
                        escala = progreso_pop

                self._dibujar_ficha_en_rect(surface, _rect_celda(fila, col), valor, escala=escala)


class GameOverState(BaseState):
    """Pantalla final: victoria (2048 alcanzado) o derrota (sin movimientos)."""

    def enter(self, victoria: bool = False, puntuacion: int = 0, **kwargs) -> None:
        self.victoria = victoria
        self.puntuacion = puntuacion

        self.fuente_titulo = pygame.font.SysFont("arial", 62, bold=True)
        self.fuente_texto = pygame.font.SysFont("arial", 30)
        self.fuente_ayuda = pygame.font.SysFont("arial", 22)

    def exit(self) -> None:
        pass

    def on_input(self, input_id: str, input_data) -> None:
        if input_id == "reiniciar" and getattr(input_data, "pressed", False):
            self.state_machine.change("jugar")

    def update(self, dt: float) -> None:
        pass

    def render(self, surface: pygame.Surface) -> None:
        surface.blit(_fondo_espacial(*surface.get_size()), (0, 0))
        _dibujar_panel(surface)

        color_titulo = COLOR_VICTORIA if self.victoria else COLOR_DERROTA
        texto_titulo = "¡GANASTE!" if self.victoria else "GAME OVER"
        titulo = self.fuente_titulo.render(texto_titulo, True, color_titulo)
        rect_titulo = titulo.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 80))

        _dibujar_texto_con_resplandor(
            surface, self.fuente_titulo, texto_titulo, color_titulo, COLOR_GLOW_TITULO, rect_titulo.topleft
        )

        texto_score = self.fuente_texto.render(
            f"Puntuación final: {self.puntuacion}", True, COLOR_TEXTO_PRINCIPAL
        )
        rect_score = texto_score.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2))
        surface.blit(texto_score, rect_score)

        ayuda = self.fuente_ayuda.render(
            "Presiona R para reiniciar   |   ESC para salir", True, COLOR_TEXTO_TENUE
        )
        rect_ayuda = ayuda.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 65))
        surface.blit(ayuda, rect_ayuda)
