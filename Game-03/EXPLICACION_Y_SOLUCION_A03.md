# Desafío A03 — explicación y solución

> Este archivo vive dentro de `cubo_rubik/` (la versión **completa**,
> no la tarea) a propósito: `cubo_rubik_tarea/` no tiene ninguna copia
> de esto, para que siga sirviendo como ejercicio. Es lo mismo que ya
> está implementado en `src/algorithm.py` de este mismo proyecto,
> reunido acá en un solo lugar con la explicación al lado.

## ¿De qué se trata?

El enunciado, tal cual:

> Busca una matriz tridimensional de enteros dentro de una matriz
> tridimensional más grande, desplazando la matriz más pequeña por
> todas las posiciones válidas de la matriz más grande. En cada
> posición candidata, realiza una comparación completa elemento por
> elemento para comprobar si hay una coincidencia exacta de todo el
> bloque tridimensional, pasando a la siguiente posición candidata si
> se encuentra un elemento que no coincide.
>
> **Key Concept:** Recorrido por una matriz 3D.
> **Enfoque en la comprensión:** Reconocimiento de patrones.

Aplicado al Cubo de Rubik: `RubikCube.matriz` es la matriz 3D grande
(3x3x3), donde cada celda guarda el identificador entero de la pieza
que ocupa esa posición. La función a implementar,
`buscar_patron_3d(matriz_grande, matriz_patron)`, recibe esa matriz
grande y un bloque más chico (`matriz_patron`, por ejemplo 2x2x2) y
tiene que decir en qué posición `(x, y, z)` de la matriz grande
aparece ese bloque exacto, si es que aparece.

Es el mismo tipo de problema que buscar una palabra en una sopa de
letras, pero en 3D en vez de 2D: se toma una "ventana" del tamaño del
patrón y se la va apoyando en cada lugar posible del espacio grande;
en cada lugar donde se apoya, se revisa si calza perfecto.

## La idea, paso a paso

1. **Calcular las dimensiones** de la matriz grande y del patrón.
2. **Verificar que el patrón entra**: si el patrón es más grande que
   la matriz grande en algún eje, directamente no hay nada que
   buscar.
3. **Recorrer todas las posiciones candidatas**: todo punto
   `(origen_x, origen_y, origen_z)` de la matriz grande donde, al
   apoyar ahí el patrón, éste todavía quede completamente adentro (no
   se salga por ningún borde). Esto es "desplazar la matriz más
   pequeña por todas las posiciones válidas de la matriz más grande".
4. **Comparar elemento por elemento**: para cada posición candidata,
   comparar cada celda del bloque de la matriz grande contra la celda
   correspondiente del patrón.
   - Si **una sola celda no coincide**, esa posición ya no sirve: hay
     que **abandonarla de inmediato** (no seguir comparando el resto
     del bloque, sería trabajo de más) y pasar a la siguiente posición
     candidata.
   - Si **todas** las celdas coinciden, esa posición es la respuesta:
     se encontró el patrón ahí.
5. Si se recorrieron todas las posiciones candidatas y ninguna
   coincidió por completo, la respuesta es "no encontrado".

Ese "abandonar en cuanto una celda no coincide" es la parte que hace
que sea un algoritmo de **fuerza bruta con corte temprano**: en vez de
comparar siempre las 8 (o 12, o 27...) celdas del bloque en cada
posición, se corta la comparación ni bien se sabe que esa posición ya
no puede ser la correcta.

## Solución completa

Esto es exactamente el contenido de `src/algorithm.py` en este
proyecto (`cubo_rubik/`, la versión completa):

```python
"""
Algoritmo A03 — Búsqueda de un patrón dentro de una matriz 3D.
"""
from typing import Dict, List, Tuple

Matriz3D = List[List[List[int]]]


def _bloque_coincide(
    matriz_grande: Matriz3D,
    matriz_patron: Matriz3D,
    origen_x: int,
    origen_y: int,
    origen_z: int,
    profundidad_patron: int,
    filas_patron: int,
    columnas_patron: int,
) -> bool:
    """
    Compara, elemento por elemento, el bloque de `matriz_grande` que
    empieza en (origen_x, origen_y, origen_z) contra `matriz_patron`
    completo. Corta y devuelve False ni bien encuentra una celda que
    no coincide (no sigue comparando el resto del bloque).
    """
    for i in range(profundidad_patron):
        for j in range(filas_patron):
            for k in range(columnas_patron):
                valor_grande = matriz_grande[origen_x + i][origen_y + j][origen_z + k]
                valor_patron = matriz_patron[i][j][k]

                if valor_grande != valor_patron:
                    # Un elemento no coincide: se abandona esta posición
                    # candidata sin comparar el resto del bloque.
                    return False

    # Se compararon todas las celdas del bloque y ninguna difirió.
    return True


def buscar_patron_3d(
    matriz_grande: Matriz3D, matriz_patron: Matriz3D
) -> Dict[str, object]:
    """
    Busca `matriz_patron` dentro de `matriz_grande` por fuerza bruta.

    :returns: {'encontrado': bool, 'posicion': (x, y, z) o None}
    """
    # Paso 1: dimensiones de ambas matrices.
    profundidad_grande = len(matriz_grande)
    filas_grande = len(matriz_grande[0]) if profundidad_grande else 0
    columnas_grande = len(matriz_grande[0][0]) if filas_grande else 0

    profundidad_patron = len(matriz_patron)
    filas_patron = len(matriz_patron[0]) if profundidad_patron else 0
    columnas_patron = len(matriz_patron[0][0]) if filas_patron else 0

    # Paso 2: si el patrón no cabe, no hay nada que buscar.
    if (
        profundidad_patron > profundidad_grande
        or filas_patron > filas_grande
        or columnas_patron > columnas_grande
    ):
        return {"encontrado": False, "posicion": None}

    # Paso 3: recorrer todas las posiciones candidatas válidas.
    for origen_x in range(profundidad_grande - profundidad_patron + 1):
        for origen_y in range(filas_grande - filas_patron + 1):
            for origen_z in range(columnas_grande - columnas_patron + 1):
                # Paso 4: comparación completa elemento por elemento.
                if _bloque_coincide(
                    matriz_grande,
                    matriz_patron,
                    origen_x,
                    origen_y,
                    origen_z,
                    profundidad_patron,
                    filas_patron,
                    columnas_patron,
                ):
                    # Paso 5: coincidencia exacta de todo el bloque.
                    return {
                        "encontrado": True,
                        "posicion": (origen_x, origen_y, origen_z),
                    }
                # Si _bloque_coincide devolvió False, ya se abandonó
                # esta candidata (por el primer elemento que no
                # coincidió) y el ciclo simplemente sigue con la
                # siguiente posición.

    # Paso 6: se probaron todas las posiciones candidatas, ninguna coincidió.
    return {"encontrado": False, "posicion": None}


def buscar_todas_las_coincidencias(
    matriz_grande: Matriz3D, matriz_patron: Matriz3D
) -> List[Tuple[int, int, int]]:
    """
    Variante de `buscar_patron_3d` que no se detiene en la primera
    coincidencia: recorre igualmente todas las posiciones candidatas y
    devuelve la lista completa de posiciones donde el bloque coincide
    por completo (puede ser una lista vacía). No es obligatoria para
    el desafío A03 (que solo pide declarar una coincidencia), pero
    reutiliza el mismo criterio de comparación.
    """
    profundidad_grande = len(matriz_grande)
    filas_grande = len(matriz_grande[0]) if profundidad_grande else 0
    columnas_grande = len(matriz_grande[0][0]) if filas_grande else 0

    profundidad_patron = len(matriz_patron)
    filas_patron = len(matriz_patron[0]) if profundidad_patron else 0
    columnas_patron = len(matriz_patron[0][0]) if filas_patron else 0

    coincidencias: List[Tuple[int, int, int]] = []

    if (
        profundidad_patron > profundidad_grande
        or filas_patron > filas_grande
        or columnas_patron > columnas_grande
    ):
        return coincidencias

    for origen_x in range(profundidad_grande - profundidad_patron + 1):
        for origen_y in range(filas_grande - filas_patron + 1):
            for origen_z in range(columnas_grande - columnas_patron + 1):
                if _bloque_coincide(
                    matriz_grande,
                    matriz_patron,
                    origen_x,
                    origen_y,
                    origen_z,
                    profundidad_patron,
                    filas_patron,
                    columnas_patron,
                ):
                    coincidencias.append((origen_x, origen_y, origen_z))

    return coincidencias
```

## Cómo se usa desde el resto del proyecto

`RubikCube.search_3d_pattern` (en `src/rubik_cube.py`) es un método
delgado que solo llama a `buscar_patron_3d` con el estado actual del
cubo:

```python
def search_3d_pattern(self, target_submatrix):
    resultado = buscar_patron_3d(self.matriz, target_submatrix)
    return resultado["posicion"] if resultado["encontrado"] else None
```

Y `src/states/play_state.py` lo usa desde los botones **"Buscar patron
real (A03)"** y **"Buscar patron imposible"**, resaltando en 3D los
stickers de la posición encontrada.

## Cómo comprobar que esta solución es correcta

```bash
cd cubo_rubik
../.venv/bin/python test_search_3d_pattern.py
```

Corre 4 casos (un patrón real que debe encontrarse en su posición de
origen, ese mismo patrón después de mezclar el cubo, un patrón
imposible que nunca debe encontrarse, y un bloque más grande) y
termina con "Todos los casos de prueba terminaron correctamente." si
todo está bien — que es justo lo que pasa con este código.
