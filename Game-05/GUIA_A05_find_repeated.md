# Guía: resolver el desafío A05 — `find_repeated()`

## De qué se trata (sin dar nada por sabido)

El tablero de Transmutación Arcana guarda su estado en `Board.tiles`
(`src/board/board.py`): una matriz de 6x6, donde cada casilla tiene un
`Tile` cuyo `.kind` es uno de los 8 elementos (`TileKind`, un
`IntEnum`: Fuego=0, Agua=1, Tierra=2, Aire=3, Electricidad=4, Hielo=5,
Magia=6, Oscuridad=7). Esos valores no son fijos: cada swap que hace
el jugador reordena la matriz, así que el tablero termina "relleno"
por las jugadas del jugador, tal como describe el enunciado.

El desafío consiste en escribir una función que, dada una matriz de
enteros, devuelva **cuáles valores están repetidos** — cuáles aparecen
dos o más veces — sin importar cuántas veces se repitan ni en qué
posición.

Es el mismo tipo de problema que "encontrar los artículos que anotaste
dos veces en una lista de compras": recorrés la lista y, cada vez que
un artículo ya había aparecido antes, lo marcás como repetido (una
sola vez, aunque vuelva a aparecer una tercera o cuarta vez).

## Dónde está

Archivo `src/algorithm.py`, función `find_repeated`:

```python
def find_repeated(matrix: List[List[int]]) -> List[int]:
    ...
```

Este archivo no importa `pygame` ni `gale`: es lógica pura sobre listas
anidadas de enteros, pensada para poder leerse, probarse y calificarse
de forma aislada de la parte gráfica del juego (mismo criterio que
`src/algorithm.py` en Game-03).

## Qué tiene que hacer la función

**Entrada:** `matrix`, una lista de filas (cada fila, una lista de
enteros). No hace falta que sea cuadrada ni que todas las filas midan
lo mismo — hasta sirve pasarle una matriz de una sola fila.

**Salida:** una lista con los valores que aparecen **2 o más veces**
en `matrix`, **en el orden en que se detectó la repetición** (o sea,
en el orden de su *segunda* aparición), cada uno una sola vez sin
importar cuántas veces más se repita.

## Cómo pensar la solución

El enunciado dice "comparando cada elemento con los valores
siguientes" — la forma más directa de imaginarlo es con dos bucles
anidados: por cada elemento, mirar todos los que vienen después y
marcarlo si alguno coincide. Funciona, pero por cada elemento hay que
volver a recorrer el resto de la matriz — lento si la matriz crece.

La solución en `find_repeated` hace exactamente lo mismo pero mirado
al revés, en un solo recorrido:

1. Crear dos **conjuntos** (`set`) vacíos: `seen`, para los valores que
   ya se vieron una vez, y `reported`, para los que ya se agregaron al
   resultado (evita reportar un mismo valor más de una vez si se
   repite 3 o más veces). Y una lista vacía, `repeated`, para el
   resultado.
2. Recorrer la matriz fila por fila, y dentro de cada fila, valor por
   valor.
3. Para cada valor: si **no** está en `seen`, es la primera vez que
   aparece — se agrega a `seen` y no se hace nada más. Si **ya** está
   en `seen`, es una repetición — y si todavía no está en `reported`,
   se agrega a `reported` y también a `repeated`.
4. Al terminar de recorrer toda la matriz, `repeated` tiene la
   respuesta.

¿Por qué esto es lo mismo que "comparar cada elemento con los
siguientes"? Porque, desde el punto de vista de la **primera**
aparición de un valor, cualquier aparición posterior de ese mismo
valor es, por definición, uno de "los valores siguientes" — y el
chequeo `valor in seen` la detecta en cuanto el recorrido llega a
ella, sin tener que comparar manualmente contra cada casilla restante.
Ahí es donde entra el **Key Concept** del enunciado: usar un
`Conjunto` (`set`) es lo que convierte esa comparación en algo
inmediato (verificar si ya está adentro) en vez de un bucle interno
por cada elemento.

### Ejemplo para verificar a mano

```python
>>> find_repeated([[1, 2, 2, 3], [3, 1, 4]])
[2, 3, 1]
```

- `1` es nuevo → se guarda en `seen`, nada mas.
- `2` es nuevo → se guarda en `seen`, nada mas.
- el segundo `2` ya está en `seen` → se reporta: `repeated = [2]`.
- `3` es nuevo → se guarda en `seen`.
- el segundo `3` (al empezar la fila siguiente) ya está en `seen` →
  se reporta: `repeated = [2, 3]`.
- el segundo `1` ya está en `seen` → se reporta: `repeated = [2, 3, 1]`.
- `4` es nuevo → se guarda en `seen`, no se reporta (nunca se repite).

Resultado: `[2, 3, 1]`, en el orden en que se detectó cada repetición.

## Cómo está conectada al juego

En el Módulo A (`src/board/board.py`), la Regla de Catálisis (match-4
o más) no solo limpia el match — limpia **toda la fila o columna**
donde ocurrió, sin importar qué elementos había en el resto de esa
línea (`Board.resolve_runs`, cuando `run.is_catalysis` es `True`).

Esa fila o columna completa, con los `TileKind.value` de cada ficha,
**es** la línea del tablero que pide el enunciado (adaptado en
`src/algorithm.py`) — representada como una matriz de una sola fila,
que es la forma que entiende `find_repeated`. Justo antes de
limpiarla, `resolve_runs` arma esa lista y se la pasa a
`find_repeated`:

```python
line_kinds = [[tile.kind.value for tile in line_tiles if tile is not None]]
catalysis_resonance_kinds += len(find_repeated(line_kinds))
```

El resultado — cuántos elementos **se repitieron** dentro de esa línea
— es lo que `PlayState._process_matches` usa para pagar el bonus de
**Resonancia Elemental**: `settings.RESONANCE_BONUS_PER_KIND` por cada
elemento que apareció 2 o más veces en la línea que arrastró la
Catálisis. Una Catálisis totalmente mixta (cada elemento aparece una
sola vez, `find_repeated` devuelve una lista vacía) no paga nada
extra; una donde algún elemento se repite dentro de la misma línea sí
— premia la idea temática de que ese elemento "resuena" al aparecer
más de una vez en la misma transmutación.

## Caso de prueba integrado

```bash
.venv/bin/python test_find_repeated.py
```

No necesita ventana. Corre dos grupos de casos:

1. `find_repeated` en aislamiento (matrices sueltas, sin el tablero).
2. `Board.resolve_runs` con una Catálisis armada a mano — una línea
   totalmente mixta (sin repetidos, resonancia 0), una con dos
   elementos que se repiten cada uno una vez (resonancia 2), una línea
   homogénea (resonancia 1) y un Match-3 común (sin Catálisis, sin
   bonus) — para confirmar que el bonus de resonancia se calcula bien
   en cada caso.
