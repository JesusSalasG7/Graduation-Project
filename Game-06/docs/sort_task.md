# `sort_words_by_length` — ejercicio de ordenamiento

Archivo: [`src/algorithms/sort_task.py`](../src/algorithms/sort_task.py)

## Qué hace el módulo

`PlayState` genera una tanda de palabras reales antes de que empiece cada
partida (justo al salir de la pantalla de controles, o al reiniciar tras un
game over). Esas mismas palabras son las que se ordenan **por su
longitud**. El módulo se encarga de:

1. `generate_words(count, seed=None)` — pide `count` palabras nuevas a
   `WordStream`.
2. **`sort_words_by_length(words)`** — recibe esa lista de palabras y debe
   devolverlas ordenadas de menor a mayor longitud (`len(word)`).
3. `run_sort_words_by_length(words)` — mide cuánto tarda
   `sort_words_by_length` y nunca deja que un fallo (o una implementación
   incorrecta) tumbe el juego (ver "Qué pasa si no está implementada").

Su resultado alimenta directamente al juego: las palabras ordenadas pasan
por `group_in_ascending_blocks` (ver
[`src/algorithms/word_length_variety.py`](../src/algorithms/word_length_variety.py))
y de ahí se convierten en el `preset_words` con el que arranca la partida
-- por eso, a diferencia de otros ejercicios "de consola", este tiene efecto
visible e inmediato en cómo se juega.

## El reto: implementar `sort_words_by_length`

```python
def sort_words_by_length(words: List[str]) -> List[str]:
    pass
```

Ahora mismo `sort_words_by_length` está vacía a propósito. El reto es
escribir el cuerpo de esa función para que **ordene `words` de forma
ascendente según `len(word)`**, usando el algoritmo que se prefiera
(heapsort, quicksort, mergesort, bubble sort...). Reglas del ejercicio:

- **No debe mutar la lista que recibe.** Conviene trabajar sobre una copia
  o construir listas nuevas, no ordenar `words` en el sitio.
- **Debe devolver una lista nueva** con las mismas palabras que entraron
  (incluyendo duplicados), del mismo tamaño, ordenada por longitud.
- Palabras de la misma longitud pueden ir en cualquier orden entre sí; no
  hace falta que el ordenamiento sea estable.
- Tiene que manejar lista vacía, una sola palabra, listas ya ordenadas,
  ordenadas al revés y listas con muchas longitudes repetidas (las
  longitudes de palabra en este juego solo varían entre un puñado de
  valores distintos -- ver `SHORT_WORD_LENGTH_RANGE` /
  `LONG_WORD_LENGTH_RANGE` en `settings.py` -- así que los duplicados son
  el caso común, no el borde).
- No hace falta preocuparse por rendimiento: `settings.SORT_TASK_WORD_COUNT`
  son solo 500 palabras, cualquier algoritmo correcto termina en menos de
  un milisegundo.

Es la única función que el resto del juego llama para este ejercicio (ver
`PlayState._begin_sort_task`), así que cualquier ordenamiento correcto que
se ponga ahí dentro es suficiente -- nada más en el juego necesita cambiar.

### Qué pasa si se deja sin implementar (o mal implementada)

El módulo está diseñado para que dejarla vacía (`pass`, que implícitamente
devuelve `None`), que lance una excepción, o que devuelva algo que no sea
una lista de strings, sea **seguro**: `run_sort_words_by_length` atrapa los
tres casos y devuelve `(None, 0.0 o elapsed)` en vez de propagar el error o
dejar pasar un resultado corrupto. Cuando eso pasa, `PlayState` se salta
la pantalla de carga del ordenamiento y arranca la partida de inmediato
-- pero **con el mismo lote de palabras ya generado y deduplicado**,
solo que en el orden en que se generaron, no ordenado ni agrupado por
bloques. Es decir: no hace falta implementarla para poder jugar, y el
lote de palabras no se pierde ni se descarta; lo único que cuesta no
implementarla (o implementarla mal) es la pantalla "N palabras ordenadas
en X ms" y el orden ascendente de las palabras al caer.

Nota: esta validación de tipo NO comprueba que el resultado esté
efectivamente bien ordenado -- solo evita que el juego explote por un tipo
de dato inesperado. Un ordenamiento mal implementado pero que devuelve una
lista de strings del tamaño correcto pasará sin error y simplemente se
verá en pantalla como palabras en el orden equivocado; para verificar que
el ordenamiento en sí es correcto, usa los tests.

## Cómo probarla aparte (fuera del juego)

Los tests están en [`tests/test_sort_task.py`](../tests/test_sort_task.py)
y son completamente independientes de Pygame/PlayState -- solo importan el
módulo y comparan contra `sorted(words, key=len)`. Para correrlos:

```bash
pytest tests/test_sort_task.py -v
```

Cubren, entre otros:

- Que ordena una lista aleatoria de palabras igual que
  `sorted(words, key=len)`.
- Lista vacía y de una sola palabra.
- Ya ordenada / ordenada al revés.
- Muchas longitudes repetidas (el caso realista de este juego).
- Que no muta ni pierde/duplica palabras.
- `run_sort_words_by_length` devuelve `(sorted, elapsed>=0)` cuando
  `sort_words_by_length` sí está implementada, y `(None, ...)` cuando está
  en `pass`, lanza una excepción, o devuelve un tipo inválido (estos casos
  usan `monkeypatch` para simularlo sin depender de si ya la
  implementaste o no).

También se puede probar a mano desde una consola de Python, sin pytest:

```bash
python -c "
from src.algorithms.sort_task import sort_words_by_length
print(sort_words_by_length(['HOLA', 'SI', 'MUNDO', 'A']))
"
```

## Cómo probarla dentro del juego

1. Arranca el juego normalmente (revisa el `README.md` del proyecto para
   el comando exacto, típicamente `python main.py`).
2. Desde la pantalla de portada, entra a una partida (se pasa primero por
   la pantalla de controles).
3. Justo antes de que empiece a caer la primera palabra, `PlayState`
   llama a `_begin_sort_task`, que genera `SORT_TASK_WORD_COUNT` (500)
   palabras, las deduplica y se las pasa a `sort_words_by_length` vía
   `run_sort_words_by_length`.
4. **Si `sort_words_by_length` está implementada correctamente**, aparece
   una pantalla de carga con el resultado ("N palabras ordenadas en X
   ms") durante `settings.SORT_LOADING_DISPLAY_SECONDS` (1.5 s por
   defecto), y la partida arranca con las palabras presentadas en orden
   ascendente de longitud (agrupadas de a `WORD_LENGTH_BLOCK_SIZE` por
   tanda, ver `src/algorithms/word_length_variety.py`).
5. **Si `sort_words_by_length` sigue en `pass` (lanza una excepción, o
   devuelve algo que no es una lista de strings)**, esa pantalla de carga
   no aparece -- la partida arranca de inmediato con el mismo lote de
   palabras generado y deduplicado, pero sin ordenar ni agrupar por
   bloques (en el orden en que salieron de `generate_words`). Esta es la
   señal más rápida en el juego de que la implementación aún falta o
   tiene un error de tipo.
6. También se puede reiniciar tras un game over para repetir la
   comprobación: `_begin_sort_task` se vuelve a llamar en cada reinicio,
   con una tanda de palabras nueva.
