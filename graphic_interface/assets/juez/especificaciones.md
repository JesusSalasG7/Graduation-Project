# Especificaciones de referencia de los desafíos

## Uso de este documento

Cada ficha define lo que un prompt completo debe comunicar para que una IA aislada (que no ve el enunciado ni el código del juego) implemente la función correctamente. El juez recibe la ficha junto con el prompt del participante y puntúa qué elementos aparecen.

Cada ficha tiene seis partes:

- **Firma**: nombre, parámetros, tipos y retorno.
- **Comportamiento esperado**: qué debe hacer la función.
- **Restricciones de implementación**: cómo debe hacerlo (complejidad, qué usar y qué no). La IA no las conoce si el prompt no las menciona.
- **Casos borde**: situaciones límite que un buen prompt anticipa.
- **Contexto que la IA necesita**: nombres de atributos, métodos auxiliares o estructuras del juego que la IA no puede adivinar.
- **Errores típicos de comprensión**: lo que suele indicar que el participante no entendió.

Las fichas están contrastadas con `graphic_interface/content/challenges.py` (el enunciado que ve el participante) y con el código de cada juego. Si cambia un enunciado, hay que actualizar su ficha y subir `JUDGE_TEMPLATE_VERSION` en `judge/judge_config.py`.

## Game-01 · Conteo de manzanas en rango

**Ubicación:** `src/world.py` → `World.count_apples_in_range()`

**Firma:** `def count_apples_in_range(self) -> int`

**Comportamiento esperado**

- Cuenta cuántas manzanas del tablero tienen un valor dentro del filtro activo `[filter_min, filter_max]`, con ambos límites incluidos.
- Cada manzana tiene un valor entero: -5, 5 o 15.
- El resultado es lo que muestra el indicador "En rango: N/Total"; no suma puntos ni cambia nada del juego.

**Restricciones de implementación**

- Recorrer todas las manzanas de `self.food_field.apples`.
- Decidir si cada manzana cuenta llamando a `self._apple_passes_filter(apple.value)`, sin comparar el rango a mano.
- Devolver un `int`, en tiempo O(n) con una sola pasada sobre la lista.
- No mutar `self.food_field.apples` ni otros atributos de `self`.

**Casos borde**

- Sin manzanas → 0.
- Valores justo en los límites del rango (cuentan, porque es inclusivo).

**Ejemplos** (seis manzanas con valores `[-5, 5, 15, 5, -5, 15]`)

| Rango | Resultado |
| --- | --- |
| \[0, 10\] | 2 |
| \[-5, 5\] | 4 |
| \[-5, 15\] | 6 |
| \[10, 20\] | 2 |

**Contexto que la IA necesita:** que es un método de la clase `World`, que las manzanas están en `self.food_field.apples`, que el valor está en `apple.value` y que existe `self._apple_passes_filter()`.

**Errores típicos:** reimplementar la comparación del rango; usar límites exclusivos; devolver la lista de manzanas en vez del número; modificar el estado del mundo.

## Game-02 · Comprimir y fusionar línea (2048)

**Ubicación:** `src/logic2048.py` → `Board._compress_and_merge(line)`

**Firma:**

```python
def _compress_and_merge(
    line: List[int],
) -> Tuple[List[int], int, bool, List[_LineShift]]:
```

**Comportamiento esperado**

- Recibe una fila o columna del tablero ya orientada: el primer elemento es el extremo hacia el que se desliza.
- Comprime las fichas hacia el principio de la línea, sin cambiar su orden relativo.
- Fusiona pares de fichas iguales contiguas; cada ficha se fusiona como máximo una vez por movimiento.
- Rellena con ceros hasta el tamaño original.
- Devuelve una tupla con: la nueva línea, los puntos obtenidos (suma de los valores creados por fusión), si hubo cambio (False si el resultado es idéntico a la entrada) y un registro de desplazamiento por cada ficha original (índice de origen, destino, valor y si se fusionó).

**Restricciones de implementación**

- No mutar la lista de entrada.

**Casos borde**

- Cuatro fichas iguales: `[2,2,2,2]` da `[4,4,0,0]`, no `[8,0,0,0]`.
- Tres iguales seguidas: se fusionan las dos primeras.
- Línea que no cambia: `hubo_cambio` debe ser False.
- Desplazamiento sin fusión: cuenta como cambio.

**Ejemplos**

| Entrada | Nueva línea | Puntos | Hubo cambio |
| --- | --- | --- | --- |
| \[2, 2, 2, 4\] | \[4, 2, 4, 0\] | 4 | True |
| \[2, 2, 2, 2\] | \[4, 4, 0, 0\] | 8 | True |
| \[4, 0, 0, 2\] | \[4, 2, 0, 0\] | 0 | True |
| \[8, 4, 2, 0\] | \[8, 4, 2, 0\] | 0 | False |

**Contexto que la IA necesita:** que la línea ya viene orientada, la estructura exacta de la tupla de retorno y el formato del registro de desplazamientos.

**Errores típicos:** fusionar en cascada (`[2,2,2,2]` → `[8]`); fusionar desde el final de la línea; olvidar rellenar con ceros; contar puntos de fichas que no se fusionaron; marcar cambio cuando la línea queda igual.

Los tests de referencia están en `Game-02/tests/test_logic2048.py`.

## Game-03 · Búsqueda de patrón 3D (fuerza bruta)

**Ubicación:** `src/algorithm.py` → `find_3d_pattern(big_matrix, pattern_matrix)`

**Firma:**

```python
Matrix3D = List[List[List[int]]]

def find_3d_pattern(
    big_matrix: Matrix3D, pattern_matrix: Matrix3D
) -> Dict[str, object]:
```

**Comportamiento esperado**

- Busca la matriz 3D pequeña (`pattern_matrix`) dentro de la grande (`big_matrix`), probando todas las posiciones válidas.
- Devuelve un diccionario con dos claves: `"found"` (True/False) y `"position"` (la tupla `(x, y, z)` de la primera coincidencia, o None si no hay).
- La primera coincidencia se define recorriendo las posiciones en orden x, luego y, luego z.
- Contexto del juego: el estado 3x3x3 del cubo de Rubik (`RubikCube.matrix`) y un bloque más pequeño, por ejemplo 2x2x2.

**Restricciones de implementación**

- Fuerza bruta, sin otras optimizaciones: recorrer todas las posiciones candidatas y comparar elemento por elemento.
- En cada posición, pasar a la siguiente en cuanto una celda no coincida.
- Al encontrar una coincidencia, devolverla de inmediato, sin seguir buscando.
- No asumir matrices cúbicas ni de tamaño fijo.
- No lanzar excepciones.

**Casos borde**

- Patrón más grande que la matriz en cualquier eje → `{"found": False, "position": None}`.
- Patrón no cúbico, por ejemplo 3x3x2.
- Patrón con un valor que no existe en la matriz (por ejemplo 99) → nunca se encuentra.

**Ejemplos**

- Un bloque 2x2x2 extraído de la esquina (0,0,0) de un cubo resuelto (3x3x3) se encuentra en (0,0,0).
- Un bloque 3x3x2 extraído de un cubo recién reiniciado se encuentra en su posición de origen.
- Un patrón relleno con 99 no se encuentra.

**Contexto que la IA necesita:** el formato de `matriz[i][j][k]` (listas anidadas de 3 niveles con enteros), las claves exactas del diccionario y que `position` es una tupla `(x, y, z)`.

**Errores típicos:** recorrer solo hasta el tamaño de la matriz grande y salirse del índice; buscar solo en 2D; seguir buscando tras la primera coincidencia; devolver una lista o un booleano en vez del diccionario; lanzar excepción cuando el patrón no cabe.

## Game-04 · Verificar señal estable (palíndromo)

**Ubicación:** `src/signal_check.py` → `is_stable_signal(text)`

**Firma:** `def is_stable_signal(text: str) -> bool`

**Comportamiento esperado**

- Devuelve True si la señal se lee igual al revés ("conserva su patrón") y False si no ("se altera").
- En el juego, el jugador tiene 4 segundos para decidir con esta misma regla, que nunca se explica: el participante debe deducir que se trata de un palíndromo.

**Restricciones de implementación**

- Devolver un `bool` puro (no un valor "truthy" cualquiera), sin efectos secundarios ni mutar nada.
- Comparación carácter por carácter: distingue mayúsculas de minúsculas e incluye espacios y símbolos, sin normalizar nada.
- No depender de pygame ni del estado del juego; no usar bibliotecas: lógica pura sobre un string.

**Casos borde**

- Cadena vacía `""` → True.
- Un solo carácter → True.
- Mayúsculas y minúsculas mezcladas o espacios: no se normalizan.

**Ejemplos**

| Resultado | Señales |
| --- | --- |
| True | RADAR, RECONOCER, SOMETEMOS, ANILINA, ROTOR, SALAS, SOMOS, SERES |
| False | CÓDIGO, PYTHON, JUEGO, SISTEMAS, VENTANA, TELÉFONO, MENSAJE, CIRCUITO |

**Contexto que la IA necesita:** solo la firma y la regla. Como la regla no se explica en el juego, nombrar "palíndromo" o describirla bien es la principal evidencia de comprensión.

**Errores típicos:** normalizar a minúsculas o quitar espacios; devolver un string en vez de un booleano; tratar la cadena vacía como inestable; describir la regla de otra forma (por ejemplo, "empieza y termina con la misma letra").

## Game-05 · Detectar repetidos con conjuntos

**Ubicación:** `src/algorithm.py` → `find_repeated(matrix)`

**Firma:** `def find_repeated(matrix: List[List[int]]) -> List[int]`

**Comportamiento esperado**

- Recorre la matriz fila por fila y devuelve los valores que aparecen 2 o más veces.
- Cada valor aparece una sola vez en el resultado, aunque se repita más.
- El orden del resultado es el de la **segunda** aparición de cada valor durante el recorrido.
- Contexto del juego (Transmutación): tablero 6x6 de fichas `TileKind` representadas como enteros del 0 al 7; la Catálisis limpia una fila o columna completa, que llega como una matriz de una fila.

**Restricciones de implementación**

- Usar conjuntos (`set`; por ejemplo, uno de valores vistos y otro de valores ya reportados) para detectar repeticiones en una sola pasada.
- No comparar elemento contra elemento en O(n²).

**Casos borde**

- No asumir matriz cuadrada ni filas del mismo largo.
- Matriz de una sola fila.
- Valor que se repite tres o más veces: aparece una vez.
- Sin repetidos → lista vacía.

**Ejemplo**

- `find_repeated([[1, 2, 2, 3], [3, 1, 4]])` → `[2, 3, 1]`, en ese orden exacto: el 2 se repite primero, luego el 3 y luego el 1; el 4 nunca se repite y no aparece.

**Contexto que la IA necesita:** el criterio de orden (segunda aparición) y la exigencia de usar un conjunto; sin esto la IA probablemente ordena o usa `Counter`.

**Errores típicos:** ordenar por primera aparición o por valor; devolver duplicados del mismo valor; usar `Counter` o doble bucle; no recorrer fila por fila.

## Game-06 · Ordenar palabras por longitud

**Ubicación:** `src/algorithms/sort_task.py` → `sort_words_by_length(words)`

**Firma:** `def sort_words_by_length(words: List[str]) -> List[str]`

**Comportamiento esperado**

- Recibe la lista de palabras que genera `PlayState` antes de cada partida; el resultado determina el orden en que caen las palabras.
- Devuelve una lista **nueva** con todas las palabras, incluidos los duplicados, ordenadas de menor a mayor longitud.
- Palabras de la misma longitud pueden quedar en cualquier orden entre sí: no se exige orden estable (el enunciado y los requisitos lo dicen explícitamente).

**Restricciones de implementación**

- Implementar un algoritmo de ordenamiento propio (se recomienda mergesort, heapsort o quicksort).
- No usar `sorted()` ni `list.sort()`.
- No mutar la lista original: trabajar sobre una copia o construir listas nuevas.
- Misma cantidad de elementos que la entrada, sin perder ni duplicar palabras.
- No lanzar excepciones con entradas válidas.

**Casos borde**

- Lista vacía y lista de una palabra.
- Lista ya ordenada y lista en orden inverso.
- Muchas palabras con longitudes repetidas (el caso más común en este juego, no un caso borde).

**Criterio de verificación:** las longitudes del resultado deben coincidir con las de `sorted(words, key=len)`, aunque el orden interno entre palabras de igual longitud difiera.

**Contexto que la IA necesita:** la prohibición de `sorted()` y `list.sort()`, y que la lista original no se modifica.

**Errores típicos:** usar `sorted()`; ordenar alfabéticamente o de mayor a menor; eliminar duplicados; ordenar la lista original en el lugar.

## Game-07 · Siguiente generación de Conway con paredes

**Ubicación:** `src/board.py` → `next_generation(matrix, blocked)`

**Firma:**

```python
def next_generation(
    matrix: List[List[bool]], blocked: Set[Coord] = frozenset()
) -> List[List[bool]]:
```

**Comportamiento esperado**

- Calcula la siguiente generación del autómata con las reglas clásicas de Conway (B3/S23).
- Una celda viva con 2 o 3 vecinas vivas sobrevive.
- Una celda muerta con exactamente 3 vecinas vivas nace.
- Cualquier otra celda queda muerta.
- Las coordenadas en `blocked` son paredes: siempre quedan muertas, sin importar las reglas.

**Restricciones de implementación**

- Devolver una matriz nueva con las mismas filas y columnas, sin mutar la original.
- Calcular toda la generación a partir de la anterior, nunca con valores ya actualizados.
- Vecinos = las 8 celdas alrededor, incluidas las diagonales.
- Las posiciones fuera del borde no cuentan como vecinas (sin envolver los bordes).
- Funcionar con matrices vacías o rectangulares de cualquier tamaño, no solo cuadradas.

**Casos borde**

- Matriz vacía.
- Celdas en bordes y esquinas.
- Celda bloqueada con exactamente 3 vecinas: queda muerta.
- Celda viva rodeada por 8 vivas: muere.

**Ejemplos**

- Con `blocked` vacío, un blinker horizontal de 3 celdas pasa a vertical y luego vuelve a horizontal.
- Una celda viva completamente aislada (sin vecinas vivas) muere en la siguiente generación.
- Una coordenada en `blocked` queda muerta aunque tenga exactamente 3 vecinas vivas.
- Una celda muerta con 3 vecinas nace, aunque esas vecinas mueran en la misma generación.

**Contexto que la IA necesita:** que `blocked` es un conjunto de coordenadas (`Set[Coord]`; en el código `Coord = Tuple[int, int]` con orden (columna, fila), dato que el enunciado no da y por eso no es exigible al prompt), que las paredes siempre quedan muertas y que los bordes no envuelven.

**Errores típicos:** actualizar la matriz en el lugar; ignorar diagonales; tratar el tablero como toroidal; aplicar las reglas a celdas bloqueadas; contar la propia celda como vecina.
