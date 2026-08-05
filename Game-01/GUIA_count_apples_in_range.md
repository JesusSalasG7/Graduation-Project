# Guía: resolver `count_apples_in_range()`

## Dónde está

Archivo `src/world.py`, dentro de la clase `World`, alrededor de la línea 303:

```python
def count_apples_in_range(self) -> int:
    ...
```

Está justo debajo de `_apple_passes_filter`, que es la pieza que ya viene resuelta y que vas a reutilizar.

## Qué resuelve

La función debe devolver cuántas manzanas del tablero (`self.food_field.apples`)
tienen un valor (`apple.value`) dentro del rango activo
`[self.filter_min, self.filter_max]` en este instante.

Ya existe un método que responde esa pregunta para **una sola** manzana:
`self._apple_passes_filter(apple.value)` (devuelve `True`/`False`). No hace
falta reimplementar esa comparación -- solo usarla una vez por manzana y
llevar la cuenta de cuántas veces da `True`.

Este número alimenta dos cosas del juego (no hace falta tocarlas, solo saber
que dependen de esto):
- El HUD `En rango: N/Total` (`src/rendering/world_renderer.py`).
- El bono periódico de puntos (`World._update_range_bonus`).

### Ejemplo para verificar a mano

Con estas 6 manzanas en el tablero (mismo orden en que aparecen en
`food_field.apples`):

```
valores = [-5, +5, +15, +5, -5, +15]
```

| Filtro activo | `count_apples_in_range()` esperado | Por qué                         |
|----------------|--------------------------------------|----------------------------------|
| `[0, 10]`      | 2                                     | solo los dos `+5`                |
| `[-5, 5]`      | 4                                     | los dos `-5` y los dos `+5`       |
| `[-5, 15]`     | 6                                     | las 6 manzanas                    |
| `[10, 20]`     | 2                                     | solo los dos `+15`                |

## Cómo probar los tests sin jugar

Los tests viven en `tests/test_world_count_apples_in_range.py`. Arman un
`World` en Modo Desafío, le reemplazan las manzanas por valores fijos
(en vez de los aleatorios de una partida real) y comparan
`count_apples_in_range()` contra el resultado esperado -- incluye la tabla
del ejemplo de arriba, más casos de borde (tablero vacío, ninguna manzana en
rango, todas en rango, límites inclusivos).

Desde la raíz del proyecto (`Game-01`):

```bash
.venv/bin/pytest -v
```

(o solo `pytest -v` si activaste el entorno con `source .venv/bin/activate`)

- **Si ves `1 passed` y 11 `FAILED` con `assert None == ...`**: la función
  todavía tiene el `pass` del TODO -- no está resuelta.
- **Si ves `12 passed`**: tu implementación está bien. No necesitas abrir el
  juego para confirmarlo.

Para correr un solo caso puntual, por ejemplo el de límites inclusivos:

```bash
.venv/bin/pytest tests/test_world_count_apples_in_range.py::test_bounds_are_inclusive -v
```

`tests/conftest.py` y `pytest.ini` ya se encargan de que `pytest` funcione
sin pasos extra (sin variables de entorno, sin indicar la carpeta).
