"""
logic2048.py

Lógica pura del juego 2048 (sin ninguna dependencia de Pygame ni de Gale),
para que sea trivial de probar de forma aislada. La clase Tablero
mantiene la matriz 4x4, la puntuación y las banderas de victoria/derrota.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

TAMANO = 4
PROBABILIDAD_FICHA_2 = 0.9  # 90% de probabilidad de '2', 10% de '4'.
VALOR_VICTORIA = 2048

DIRECCIONES_VALIDAS = ("IZQUIERDA", "DERECHA", "ARRIBA", "ABAJO")


@dataclass
class _DesplazamientoLinea:
    """
    Desplazamiento de UNA ficha dentro de una única línea (fila o columna
    ya orientada), en coordenadas relativas a esa línea (0..TAMANO-1).
    Es un detalle interno de `_comprimir_y_fusionar`; `_procesar_filas`/
    `_procesar_columnas` lo traducen a coordenadas (fila, columna) reales
    del tablero para construir un `MovimientoFicha` público.
    """

    indice_origen: int
    indice_destino: int
    valor_origen: int
    fusiono: bool  # True si esta ficha terminó fusionándose con otra en destino


@dataclass
class MovimientoFicha:
    """
    Describe, para la capa de presentación, el viaje de UNA ficha que ya
    existía en el tablero antes del movimiento: desde dónde partió y a
    dónde llegó (en coordenadas (fila, columna) reales), con qué valor
    viajaba y si su destino es el resultado de una fusión (dos fichas
    del mismo valor convergiendo en la misma celda). Con esta lista la
    interfaz puede animar el deslizamiento sin tener que adivinar nada.
    """

    origen: Tuple[int, int]
    destino: Tuple[int, int]
    valor_origen: int
    fusiono: bool


@dataclass
class ResultadoMovimiento:
    """Resultado completo de un `Tablero.mover(...)`, listo para animar."""

    hubo_cambio: bool
    movimientos: List[MovimientoFicha] = field(default_factory=list)
    posicion_ficha_nueva: Optional[Tuple[int, int]] = None
    valor_ficha_nueva: Optional[int] = None


class Tablero:
    """Estado completo de una partida de 2048."""

    def __init__(self) -> None:
        self.celdas: List[List[int]] = [[0] * TAMANO for _ in range(TAMANO)]
        self.puntuacion: int = 0
        self.gano: bool = False
        self.perdio: bool = False
        # Toda partida arranca con dos fichas.
        self.agregar_ficha_aleatoria()
        self.agregar_ficha_aleatoria()

    # ------------------------------------------------------------------
    # Generación de fichas
    # ------------------------------------------------------------------
    def celdas_vacias(self) -> List[Tuple[int, int]]:
        return [
            (fila, col)
            for fila in range(TAMANO)
            for col in range(TAMANO)
            if self.celdas[fila][col] == 0
        ]

    def agregar_ficha_aleatoria(self) -> Optional[Tuple[int, int, int]]:
        """
        Coloca un '2' (90%) o un '4' (10%) en una celda vacía al azar.
        Devuelve (fila, col, valor) de la ficha creada, o None si el
        tablero ya estaba lleno; la interfaz usa esa posición para
        animar la aparición de la ficha nueva.
        """
        vacias = self.celdas_vacias()
        if not vacias:
            return None
        fila, col = random.choice(vacias)
        valor = 2 if random.random() < PROBABILIDAD_FICHA_2 else 4
        self.celdas[fila][col] = valor
        return fila, col, valor

    # ------------------------------------------------------------------
    # Núcleo del deslizamiento y la fusión
    # ------------------------------------------------------------------
    @staticmethod
    def _comprimir_y_fusionar(
        linea: List[int],
    ) -> Tuple[List[int], int, bool, List["_DesplazamientoLinea"]]:
        """
        Corazón del algoritmo de 2048.

        Recibe una "línea" de 4 valores (una fila o una columna del
        tablero) YA ORIENTADA en la dirección del movimiento: el primer
        elemento de la lista es el más cercano al borde hacia el que se
        desliza. Devuelve una tupla:

            (linea_resultante, puntos_obtenidos, hubo_cambio, desplazamientos)

        El proceso tiene tres fases, porque fusionar dos fichas deja un
        hueco que hay que volver a compactar. Además, para poder animar
        el movimiento en la interfaz, cada ficha original que no era
        cero se rastrea desde su índice de partida hasta su índice de
        llegada (eso es lo que guarda `desplazamientos`).

        1) COMPRIMIR: se identifican los valores distintos de cero junto
           con su índice original, manteniendo su orden relativo, como
           si la "gravedad" del movimiento las empujara todas hacia el
           borde. Ej: [0,2,0,2] -> [(1,2), (3,2)].

        2) FUSIONAR: se recorre esa lista de izquierda a derecha. Si un
           valor es igual al siguiente, se combinan en una única ficha
           del doble de valor -registrando AMBOS índices de origen como
           desplazamientos hacia el mismo índice de destino, marcados
           con fusiono=True- y el recorrido avanza DOS posiciones
           (i += 2), de modo que la ficha resultante de la fusión nunca
           vuelve a evaluarse en este mismo recorrido. Esto es lo que
           garantiza la regla "una ficha sólo puede fusionarse una vez
           por turno": en una línea [2,2,2,2] el resultado es [4,4] (dos
           fusiones independientes) y no [4,2,2] ni [8,0] -- una ficha
           ya fusionada jamás vuelve a sumarse con su vecina en el mismo
           movimiento.

        3) RECOMPACTAR: la fusión acorta la lista (dos fichas pasan a
           ser una), así que se rellena con ceros hasta volver a tener
           TAMANO elementos, dejando los huecos al final (lejos del
           borde hacia el que se deslizó).
        """
        # Guardamos la línea tal cual llegó (antes de tocar nada) para al
        # final poder comparar y saber si el movimiento tuvo algún efecto.
        # Ejemplo guía que seguimos en cada paso: linea = [2, 2, 2, 4]
        original = list(linea)

        # -------------------------------------------------------------
        # PASO 1 — COMPRIMIR (quitar los huecos, sin perder de dónde
        # venía cada ficha).
        #
        # `enumerate(linea)` recorre la línea dando (índice, valor) para
        # cada posición: (0,2) (1,2) (2,2) (3,4). Filtramos los ceros
        # porque una celda vacía no es una "ficha": no debe ocupar
        # espacio ni participar en la fusión.
        #
        # El resultado es una lista de PARES (índice_original, valor)
        # -no solo los valores- porque más adelante necesitamos poder
        # decir "la ficha que estaba en la posición X terminó en la
        # posición Y", y para eso hay que conservar el índice original.
        #
        # Con linea = [2, 2, 2, 4] (sin ceros que filtrar en este caso):
        #   no_ceros = [(0, 2), (1, 2), (2, 2), (3, 4)]
        # -------------------------------------------------------------
        no_ceros = [(indice, valor) for indice, valor in enumerate(linea) if valor != 0]

        # -------------------------------------------------------------
        # PASO 2 — FUSIONAR, recorriendo `no_ceros` de izquierda a
        # derecha con un índice manual `i` (no un for) porque necesitamos
        # poder "saltar de a dos" cuando ocurre una fusión.
        #
        #   fusionada      -> los valores ya resueltos, en el orden final.
        #   desplazamientos -> un registro por CADA ficha original: de
        #                      qué índice partió, a qué índice llegó, con
        #                      qué valor viajaba, y si se fusionó.
        #   puntos_obtenidos -> suma de los valores nuevos creados por
        #                       cada fusión (regla oficial de 2048: la
        #                       puntuación sube en el valor resultante).
        # -------------------------------------------------------------
        fusionada: List[int] = []
        desplazamientos: List[_DesplazamientoLinea] = []
        puntos_obtenidos = 0
        i = 0
        while i < len(no_ceros):
            indice_origen, actual = no_ceros[i]

            # ¿La siguiente ficha en la lista (si existe) tiene el MISMO
            # valor que la actual? Si es así, ambas se fusionan.
            siguiente_existe = i + 1 < len(no_ceros)
            hay_fusion = siguiente_existe and no_ceros[i + 1][1] == actual

            if hay_fusion:
                # --- Caso A: fusión de dos fichas iguales ---
                indice_origen_siguiente, _ = no_ceros[i + 1]
                valor_fusionado = actual * 2

                # `indice_destino` es simplemente "la próxima posición
                # libre en el resultado", es decir cuántos elementos ya
                # llevamos escritos en `fusionada` hasta ahora.
                indice_destino = len(fusionada)

                # Escribimos UNA sola ficha en el resultado (el doble de
                # valor), pero registramos DOS desplazamientos -uno por
                # cada ficha original que participó- apuntando ambos al
                # mismo índice de destino. Así, más adelante, la interfaz
                # puede animar cómo las dos fichas viajan y "chocan" en
                # la misma celda. Ambos quedan marcados fusiono=True.
                fusionada.append(valor_fusionado)
                puntos_obtenidos += valor_fusionado
                desplazamientos.append(
                    _DesplazamientoLinea(indice_origen, indice_destino, actual, True)
                )
                desplazamientos.append(
                    _DesplazamientoLinea(indice_origen_siguiente, indice_destino, actual, True)
                )

                # Avanzamos DOS posiciones (no una): la ficha resultante
                # de la fusión ya quedó escrita y NO vuelve a evaluarse
                # en este mismo recorrido. Esto es lo que impide que una
                # ficha se fusione dos veces en el mismo movimiento.
                i += 2
            else:
                # --- Caso B: la ficha actual queda tal cual, sin fusión ---
                indice_destino = len(fusionada)
                fusionada.append(actual)
                desplazamientos.append(
                    _DesplazamientoLinea(indice_origen, indice_destino, actual, False)
                )
                i += 1  # Solo avanzamos una posición: no se consumió ninguna otra ficha.

        # Trazando el ejemplo linea = [2, 2, 2, 4] con el bucle de arriba:
        #   i=0: no_ceros[1] también vale 2 -> FUSIÓN. fusionada=[4].
        #        desplazamientos: (0->0, val=2, fusiono=True)
        #                         (1->0, val=2, fusiono=True)
        #        i pasa a 2.
        #   i=2: no_ceros[3] vale 4 (distinto de 2) -> SIN fusión.
        #        fusionada=[4, 2]. desplazamientos += (2->1, val=2, fusiono=False)
        #        i pasa a 3.
        #   i=3: es la ficha de valor 4, no hay i+1 -> SIN fusión.
        #        fusionada=[4, 2, 4]. desplazamientos += (3->2, val=4, fusiono=False)
        #        i pasa a 4, el bucle termina (4 == len(no_ceros)).

        # -------------------------------------------------------------
        # PASO 3 — RECOMPACTAR al tamaño original de la línea.
        #
        # `fusionada` puede haber quedado más corta que `linea` (cada
        # fusión reduce el conteo en uno), así que rellenamos con ceros
        # al final -lejos del borde hacia el que se deslizó- hasta
        # recuperar la longitud original.
        #
        # Siguiendo el ejemplo: fusionada=[4,2,4] con len(linea)=4
        #   -> resultado = [4, 2, 4] + [0]*(4-3) = [4, 2, 4, 0]
        # -------------------------------------------------------------
        resultado = fusionada + [0] * (len(linea) - len(fusionada))

        # Si el resultado es idéntico a la línea de entrada, el
        # movimiento no tuvo ningún efecto en esta fila/columna (por
        # ejemplo, deslizar hacia la izquierda una línea que ya está
        # pegada a la izquierda y sin fusiones posibles).
        hubo_cambio = resultado != original
        return resultado, puntos_obtenidos, hubo_cambio, desplazamientos

    @staticmethod
    def _indice_real(indice_linea: int, invertir: bool) -> int:
        """Traduce un índice dentro de una línea (posiblemente invertida) a su índice real en el tablero."""
        return indice_linea if not invertir else TAMANO - 1 - indice_linea

    def _procesar_filas(self, invertir: bool) -> Tuple[bool, List[MovimientoFicha]]:
        """Aplica el deslizamiento horizontal (IZQUIERDA/DERECHA) fila a fila."""
        hubo_cambio_general = False
        movimientos: List[MovimientoFicha] = []

        for fila in range(TAMANO):
            linea = self.celdas[fila][:]
            if invertir:
                linea = linea[::-1]

            resultado, puntos, hubo_cambio, desplazamientos = self._comprimir_y_fusionar(linea)

            if not hubo_cambio:
                continue

            hubo_cambio_general = True
            self.puntuacion += puntos
            for d in desplazamientos:
                col_origen = self._indice_real(d.indice_origen, invertir)
                col_destino = self._indice_real(d.indice_destino, invertir)
                movimientos.append(
                    MovimientoFicha((fila, col_origen), (fila, col_destino), d.valor_origen, d.fusiono)
                )

            if invertir:
                resultado = resultado[::-1]
            self.celdas[fila] = resultado

        return hubo_cambio_general, movimientos

    def _procesar_columnas(self, invertir: bool) -> Tuple[bool, List[MovimientoFicha]]:
        """Aplica el deslizamiento vertical (ARRIBA/ABAJO) columna a columna."""
        hubo_cambio_general = False
        movimientos: List[MovimientoFicha] = []

        for col in range(TAMANO):
            linea = [self.celdas[fila][col] for fila in range(TAMANO)]
            if invertir:
                linea = linea[::-1]

            resultado, puntos, hubo_cambio, desplazamientos = self._comprimir_y_fusionar(linea)

            if not hubo_cambio:
                continue

            hubo_cambio_general = True
            self.puntuacion += puntos
            for d in desplazamientos:
                fila_origen = self._indice_real(d.indice_origen, invertir)
                fila_destino = self._indice_real(d.indice_destino, invertir)
                movimientos.append(
                    MovimientoFicha((fila_origen, col), (fila_destino, col), d.valor_origen, d.fusiono)
                )

            if invertir:
                resultado = resultado[::-1]
            for fila in range(TAMANO):
                self.celdas[fila][col] = resultado[fila]

        return hubo_cambio_general, movimientos

    # ------------------------------------------------------------------
    # API pública de movimiento
    # ------------------------------------------------------------------
    def mover(self, direccion: str) -> ResultadoMovimiento:
        """
        Ejecuta un movimiento completo: desliza+fusiona el tablero en
        `direccion`, y si hubo cambio, agrega una ficha nueva y
        recalcula las banderas de victoria/derrota.

        Devuelve un ResultadoMovimiento: si `hubo_cambio` es False, el
        tablero no se tocó (no se gasta turno ni se genera ficha nueva).
        Si es True, trae además la lista de MovimientoFicha (para animar
        el deslizamiento) y la posición/valor de la ficha nueva
        (para animar su aparición DESPUÉS del deslizamiento).
        """
        if direccion not in DIRECCIONES_VALIDAS:
            raise ValueError(f"dirección inválida: {direccion!r}")

        if self.perdio or self.gano:
            return ResultadoMovimiento(hubo_cambio=False)

        if direccion == "IZQUIERDA":
            hubo_cambio, movimientos = self._procesar_filas(invertir=False)
        elif direccion == "DERECHA":
            hubo_cambio, movimientos = self._procesar_filas(invertir=True)
        elif direccion == "ARRIBA":
            hubo_cambio, movimientos = self._procesar_columnas(invertir=False)
        else:  # "ABAJO"
            hubo_cambio, movimientos = self._procesar_columnas(invertir=True)

        if not hubo_cambio:
            return ResultadoMovimiento(hubo_cambio=False)

        if any(valor >= VALOR_VICTORIA for fila in self.celdas for valor in fila):
            self.gano = True

        ficha_nueva = self.agregar_ficha_aleatoria()

        if not self._hay_movimientos_posibles():
            self.perdio = True

        posicion_ficha_nueva = (ficha_nueva[0], ficha_nueva[1]) if ficha_nueva else None
        valor_ficha_nueva = ficha_nueva[2] if ficha_nueva else None
        return ResultadoMovimiento(
            hubo_cambio=True,
            movimientos=movimientos,
            posicion_ficha_nueva=posicion_ficha_nueva,
            valor_ficha_nueva=valor_ficha_nueva,
        )

    def _hay_movimientos_posibles(self) -> bool:
        """Game Over sólo si el tablero está lleno Y no hay fusiones posibles."""
        if self.celdas_vacias():
            return True
        for fila in range(TAMANO):
            for col in range(TAMANO):
                valor = self.celdas[fila][col]
                if col + 1 < TAMANO and self.celdas[fila][col + 1] == valor:
                    return True
                if fila + 1 < TAMANO and self.celdas[fila + 1][col] == valor:
                    return True
        return False
