# Guía: resolver el desafío A03 — `find_3d_pattern()`

## De qué se trata (sin dar nada por sabido)

El Cubo de Rubik de este juego guarda su estado en `RubikCube.matrix`
(`src/rubik_cube.py`): una matriz 3D de 3x3x3, donde cada una de las 27
celdas tiene el **identificador entero** de la pieza física que está en
esa posición (`0` es el núcleo central, `1..26` son las piezas).

El desafío consiste en escribir una función que, dado ese cubo (la
"matriz grande") y un bloque más chico de piezas (la "matriz patrón",
por ejemplo un bloque 2x2x2), diga **en qué posición `(x, y, z)`** de
la matriz grande aparece ese bloque exacto — o que no aparece en
ninguna.

Es el mismo tipo de problema que buscar una palabra dentro de una sopa
de letras, pero en 3D en vez de 2D: se apoya una "ventana" del tamaño
del patrón en cada lugar posible del cubo y, en cada lugar donde se
apoya, se revisa si calza perfecto.

## Dónde está

Archivo `src/algorithm.py`, función `find_3d_pattern`:

```python
def find_3d_pattern(
    big_matrix: Matrix3D, pattern_matrix: Matrix3D
) -> Dict[str, object]:
    ...
```

Este archivo no importa `pygame` ni `gale`: es lógica pura sobre listas
anidadas de enteros, pensada para poder leerse, probarse y calificarse
de forma aislada de la parte gráfica del juego.

## Qué tiene que hacer la función

**Entrada:**
- `big_matrix`: la matriz grande (en el juego, siempre el cubo 3x3x3,
  pero la función no debe asumir un tamaño fijo).
- `pattern_matrix`: el bloque más chico que hay que buscar adentro.

Ambas son listas anidadas de tres niveles (`matriz[i][j][k]`), no
necesariamente cúbicas.

**Salida:** un diccionario con dos claves:
- `"found"`: `True` si el patrón aparece en algún lado, `False` si no.
- `"position"`: la tupla `(origen_x, origen_y, origen_z)` de la esquina
  donde empieza la coincidencia, o `None` si no se encontró.

## Cómo pensar la solución

Esta es la explicación paso a paso, tal cual está pensada la función
(los mismos 6 pasos que vas a encontrar comentados, uno por uno, en el
cuerpo de `find_3d_pattern` una vez que la tengas resuelta -- podés
usarlos como checklist):

1. **Calcular las dimensiones** de ambas matrices (profundidad, filas
   y columnas de la matriz grande, y lo mismo para el patrón).
2. **Si el patrón no entra** en la matriz grande en algún eje, no hay
   nada que buscar: se devuelve directamente "no encontrado"
   (`found: False`, `position: None`).
3. **Recorrer TODAS las posiciones de inicio** `(origen_x, origen_y,
   origen_z)` donde el patrón, apoyado ahí, todavía cae completamente
   adentro de la matriz grande (sin salirse por ningún borde). Esto es
   "desplazar la matriz más pequeña por todas las posiciones válidas
   de la matriz más grande".
4. **En cada posición candidata, hacer una comparación completa
   elemento por elemento** para comprobar si hay una coincidencia
   exacta de todo el bloque tridimensional. Conviene resolver esta
   comparación como un paso aparte (una función auxiliar), reutilizable
   desde el recorrido principal:
   - Recorre cada celda del bloque (una celda por cada combinación de
     profundidad/fila/columna del patrón) y la compara contra la celda
     correspondiente de la matriz grande, desplazada por el origen.
   - Ni bien aparece **una sola celda que no coincide**, se corta ahí
     mismo -- no tiene sentido seguir comparando el resto del bloque,
     esa posición candidata ya se sabe inválida -- y se pasa a la
     siguiente posición candidata. Esto es justo lo que pide el
     enunciado: "pasando a la siguiente posición candidata si se
     encuentra un elemento que no coincide".
   - Si se terminan de comparar todas las celdas del bloque y ninguna
     difirió, esa posición coincide por completo.
5. **Ni bien una posición candidata coincide por completo**, esa
   coincidencia se declara encontrada y la búsqueda se detiene ahí (no
   hace falta seguir revisando el resto de las posiciones).
6. **Si se agotan todas las posiciones candidatas** sin que ninguna
   haya coincidido por completo, se declara "no encontrado".

El corte del paso 4 (abandonar la comparación ni bien una celda no
coincide, en vez de comparar siempre las 8, 12 o 27 celdas del bloque)
es lo que hace que este sea un algoritmo de **fuerza bruta con corte
temprano**.

### Ejemplo para verificar a mano

Con este cubo resuelto (recién reiniciado), el bloque 2x2x2 que ocupa
la esquina `(0, 0, 0)` tiene que encontrarse exactamente ahí:

```python
cube = RubikCube()
pattern = cube.extract_block(0, 0, 0, 2, 2, 2)
find_3d_pattern(cube.matrix, pattern)
# -> {"found": True, "position": (0, 0, 0)}
```

Si después de eso se mezcla el cubo (`cube.scramble(...)`), las piezas
cambian de posición, así que ese mismo bloque normalmente **ya no se
encuentra** en ningún lado:

```python
cube.scramble(15)
find_3d_pattern(cube.matrix, pattern)
# -> {"found": False, "position": None}   (lo más probable)
```

Y un patrón con un identificador que ninguna pieza tiene (por ejemplo,
un bloque relleno con `99`) nunca debería encontrarse, sin importar el
estado del cubo.

## Cómo se usa desde el resto del proyecto

No hace falta tocar nada de esto, solo saber que depende de la función
que estás resolviendo:

- `RubikCube.search_3d_pattern(target_submatrix)` (en
  `src/rubik_cube.py`) llama a `find_3d_pattern` con el estado actual
  del cubo y devuelve directamente `position` (o `None`).
- `src/states/play_state.py` usa ese método desde los botones/atajos de
  búsqueda de patrón, y resalta en 3D los stickers de la posición
  encontrada.

## Cómo probar tu solución sin necesidad de jugar

Hay un caso de prueba integrado, sin dependencia de `pygame`:

```bash
cd Game-03
.venv/bin/python test_search_3d_pattern.py
```

(o `python test_search_3d_pattern.py` si ya activaste el entorno con
`source .venv/bin/activate`)

Corre 4 casos por consola:

1. Un bloque 2x2x2 tomado de la esquina `(0,0,0)` del cubo resuelto →
   debe encontrarse ahí mismo.
2. Ese mismo bloque, después de mezclar el cubo → normalmente ya no se
   encuentra.
3. Un bloque imposible (relleno con el id `99`) → nunca se encuentra.
4. Un bloque más grande (3x3x2) tomado de un cubo recién reiniciado →
   debe encontrarse en su posición de origen.

Si tu implementación es correcta, termina imprimiendo:

```
All test cases finished successfully.
```

Si en cambio ves un `AssertionError` en el Caso 1 o el Caso 3, es que
`find_3d_pattern` todavía no está devolviendo lo esperado para esos
casos — son los dos que se verifican con `assert` porque su resultado
no depende del azar.
