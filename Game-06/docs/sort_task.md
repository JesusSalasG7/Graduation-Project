# `sort_task` — ejercicio de ordenamiento

Archivo: [`src/algorithms/sort_task.py`](../src/algorithms/sort_task.py)

## Qué hace el módulo

`PlayState` genera una tanda de palabras reales antes de que empiece cada
partida (justo al salir de la pantalla de controles, o al reiniciar tras un
game over). De esas palabras solo importa una cosa: **la longitud de cada
una**. El módulo se encarga de:

1. `generate_words(count, seed=None)` — pide `count` palabras nuevas a
   `WordStream`.
2. `generate_word_lengths(count, seed=None)` — igual que arriba pero
   devuelve solo las longitudes (`len(word)` de cada una); es lo que usan
   los tests cuando no importan las palabras en sí.
3. **`sort_task(lengths)`** — recibe esa lista de longitudes y debe
   devolverla ordenada de menor a mayor.
4. `run_sort_task(lengths)` — mide cuánto tarda `sort_task` y nunca deja
   que un fallo tumbe el juego (ver "Qué pasa si no está implementada").
5. `sort_words_by_length(words)` — reordena las palabras originales (no los
   números) con la misma forma de quicksort, para que la partida arranque
   con las palabras visiblemente en el mismo orden que acaba de anunciar la
   pantalla de carga.

## El reto: implementar `sort_task`

```python
def sort_task(lengths: List[int]) -> List[int]:
    pass
```

Ahora mismo `sort_task` está vacía a propósito. El reto es escribir el
cuerpo de esa función para que **ordene `lengths` de forma ascendente**,
usando el algoritmo que se prefiera (heapsort, quicksort, mergesort,
bubble sort...). Reglas del ejercicio:

- **No debe mutar la lista que recibe.** Los tests comparan el resultado
  contra `sorted(lengths)`, y conviene trabajar sobre una copia
  (`list(lengths)`) para no sorprender a quien llama.
- **Debe devolver una lista nueva ordenada**, con los mismos elementos que
  entraron (incluyendo duplicados) y del mismo tamaño.
- Tiene que manejar lista vacía, un solo elemento, listas ya ordenadas,
  ordenadas al revés y listas con muchos valores repetidos (las
  longitudes de palabra en este juego solo varían entre un puñado de
  valores distintos — ver `SHORT_WORD_LENGTH_RANGE` /
  `LONG_WORD_LENGTH_RANGE` en `settings.py` — así que los duplicados son
  el caso común, no el borde).
- No hace falta preocuparse por rendimiento: `settings.SORT_TASK_WORD_COUNT`
  son solo 500 enteros, cualquier algoritmo correcto termina en menos de
  un milisegundo.

Es la única función que el resto del juego llama para este ejercicio (ver
`PlayState._begin_sort_task`), así que cualquier ordenamiento correcto que
se ponga ahí dentro es suficiente — nada más en el juego necesita cambiar.

### Qué pasa si se deja sin implementar

El módulo está diseñado para que dejarla vacía (`pass`, que implícitamente
devuelve `None`) o que lance una excepción sea **seguro**: `run_sort_task`
atrapa ambos casos y devuelve `(None, 0.0 o elapsed)` en vez de propagar el
error. Cuando eso pasa, `PlayState` se salta por completo la pantalla de
carga del ordenamiento y arranca la partida directamente, exactamente como
se comportaba el juego antes de que existiera este ejercicio. Es decir: no
hace falta implementarla para poder jugar, pero sin implementarla nunca se
ve la pantalla "N palabras ordenadas en X ms".

## Cómo probarla aparte (fuera del juego)

Los tests están en [`tests/test_sort_task.py`](../tests/test_sort_task.py)
y son completamente independientes de Pygame/PlayState — solo importan el
módulo y comparan contra `sorted(...)`. Para correrlos:

```bash
pytest tests/test_sort_task.py -v
```

Cubren, entre otros:

- Que ordena una lista aleatoria igual que `sorted()`.
- Lista vacía y de un solo elemento.
- Ya ordenada / ordenada al revés.
- Muchos duplicados (el caso realista de longitudes de palabra).
- Que no muta ni pierde/duplica elementos.
- `run_sort_task` devuelve `(sorted, elapsed>=0)` cuando `sort_task` sí
  está implementada, y `(None, ...)` cuando está en `pass` o lanza una
  excepción (estos dos últimos casos usan `monkeypatch` para simularlo sin
  depender de si ya la implementaste o no).

También se puede probar a mano desde una consola de Python, sin pytest:

```bash
python -c "
from src.algorithms.sort_task import sort_task
print(sort_task([5, 3, 8, 3, 1]))
"
```

## Cómo probarla dentro del juego

1. Arranca el juego normalmente (revisa el `README.md` del proyecto para
   el comando exacto, típicamente `python main.py`).
2. Desde la pantalla de portada, entra a una partida (se pasa primero por
   la pantalla de controles).
3. Justo antes de que empiece a caer la primera palabra, `PlayState`
   llama a `_begin_sort_task`, que genera `SORT_TASK_WORD_COUNT` (500)
   palabras, las deduplica y les pasa las longitudes a `sort_task` vía
   `run_sort_task`.
4. **Si `sort_task` está implementada correctamente**, aparece una
   pantalla de carga con el resultado ("N palabras ordenadas en X ms")
   durante `settings.SORT_LOADING_DISPLAY_SECONDS` (1.5 s por defecto), y
   la partida arranca con las palabras presentadas en orden ascendente de
   longitud (agrupadas de a `WORD_LENGTH_BLOCK_SIZE` por tanda, ver
   `src/algorithms/word_length_variety.py`).
5. **Si `sort_task` sigue en `pass` (o lanza una excepción)**, esa
   pantalla de carga no aparece — la partida arranca de inmediato con
   palabras generadas normalmente, sin preset ordenado. Esta es la señal
   más rápida en el juego de que la implementación aún falta o tiene un
   error.
6. También se puede reiniciar tras un game over para repetir la
   comprobación: `_begin_sort_task` se vuelve a llamar en cada reinicio,
   con una tanda de palabras nueva.
