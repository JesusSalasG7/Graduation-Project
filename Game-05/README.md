# Transmutación Arcana — RPG táctico de match-3 (Pygame + gale)

RPG táctico de match-3 con temática de alquimia, hecho en Python con
[**Pygame**](https://www.pygame.org/) y el framework
[**gale**](https://pypi.org/project/gale-engine/) (manejo de estados,
ciclo del juego y UI), con la misma arquitectura de ejemplo que el
resto de proyectos de este repositorio.

Cada intercambio de fichas en el tablero es, a la vez, un hechizo: el
jugador combina fichas de 8 elementos para infligir daño directo al
enemigo o curarse, alineando 4 o más para activar la **Regla de
Catálisis** (limpia toda la fila/columna, no solo el match).

El eje central de este proyecto es el **desafío A05**: eliminar los
valores duplicados de una matriz de enteros, aplicado a las líneas que
limpia la Catálisis del propio tablero.

## Estructura

```
Game-05/
├── main.py                          # punto de entrada: crea el Game y lo ejecuta
├── settings.py                       # configuración (ventana, tablero, sprites, puntaje)
├── test_remove_duplicates.py          # caso de prueba integrado del desafío A05
├── GUIA_A05_remove_duplicates.md      # guía del desafío A05 para el participante
├── assets/graphics/
│   ├── ui/cover.jpg                   # portada de la pantalla de inicio (StartState)
│   ├── board/tiles.png                # spritesheet de los 8 iconos elementales
│   ├── portraits/                     # retratos generados por tools/generate_portraits.py
│   ├── characters/                    # hojas de sprites de jugador/enemigo
│   └── effects/                       # hojas de sprites de proyectiles/impactos
├── tools/
│   ├── generate_portraits.py          # genera los retratos de assets/graphics/portraits/
│   ├── generate_character_sprites.py  # genera las hojas de sprites de assets/graphics/characters/
│   └── generate_effect_sprites.py     # genera las hojas de sprites de assets/graphics/effects/
└── src/
    ├── transmutacion_arcana.py        # clase Game: arranca el StateMachine
    ├── algorithm.py                    # *** desafío A05: remove_duplicates *** (sin pygame)
    ├── board/                          # Módulo A -- motor del tablero
    │   ├── board.py                    # matriz, gravedad, matches, Catálisis
    │   └── tile.py                     # TileKind (los 8 elementos) y Tile
    ├── combat/                         # Módulo C -- combate RPG
    │   ├── character.py                # sprites/animación de jugador y enemigo
    │   ├── combat_manager.py           # traduce matches en daño/curación + efectos visuales + escalado de dificultad
    │   ├── elements.py                 # daño/curación/efecto de cada uno de los 8 elementos
    │   └── effects.py                  # proyectiles/impactos por elemento (pixel art)
    └── states/
        ├── start_state.py              # pantalla de inicio: portada + Enter para jugar
        └── play_state.py               # tablero + combate + puntaje (gale.state)
```

`src/algorithm.py` y `src/board/board.py` (salvo por el `pygame.Rect`
usado en `Tile.render`) son lógica sobre listas/matrices, pensada para
poder leerse, probarse y calificarse de forma aislada de lo gráfico.

## El desafío A05

> Elimina los valores duplicados de una matriz de enteros. El
> algoritmo recorre la matriz, comparando cada elemento con los
> valores siguientes y eliminando los duplicados. La matriz se rellena
> inicialmente con los valores introducidos por el usuario.
>
> **Key Concept:** Conjuntos, iteración.
> **Enfoque en la comprensión:** Filtrado de datos.

- La guía paso a paso para resolverlo, pensada para el participante
  (sin spoilear el código terminado), está en
  [`GUIA_A05_remove_duplicates.md`](GUIA_A05_remove_duplicates.md).
- La función a implementar es `src/algorithm.py::remove_duplicates`
  (lógica pura, sin depender del tablero).
- `Board.resolve_runs` (en `src/board/board.py`) es el punto de
  entrada pedido específicamente para el tablero: cada vez que una
  **Catálisis** (match-4+) limpia una fila o columna entera, esa línea
  de fichas (los `TileKind.value` de cada una, es decir, una matriz de
  enteros rellenada por las jugadas del jugador) se pasa por
  `remove_duplicates` para saber cuántos elementos **distintos**
  arrastró, y esa cantidad paga el bonus de **Diversidad Elemental**
  (`settings.DIVERSITY_BONUS_PER_KIND` por elemento distinto, sumado
  en `PlayState._process_matches`). Una Catálisis de un solo elemento
  repetido no suma nada extra; una que mezcla varios, sí.

## Caso de prueba integrado

```bash
.venv/bin/python test_remove_duplicates.py
```

No necesita ventana. Corre dos grupos de casos: `remove_duplicates` en
aislamiento (matrices sueltas) y `Board.resolve_runs` con una
Catálisis armada a mano (línea mixta, línea homogénea, y un Match-3
común sin Catálisis) para confirmar que el bonus de diversidad se
calcula bien en cada caso.

## Los 8 elementos

| Elemento | Efecto |
|---|---|
| Fuego | Daño directo |
| Agua | Cura al atacante |
| Tierra | Daño + debilita el próximo ataque rival |
| Aire | Daño directo |
| Electricidad | Daño + probabilidad de aturdir al rival |
| Hielo | Daño + debilita el próximo ataque rival |
| Magia | Daño aleatorio, con probabilidad de crítico |
| Oscuridad | Daño que ignora defensa |

Cada uno tiene su propio efecto visual en pixel art (proyectil,
impacto en el suelo, etc. — `src/combat/effects.py`), generado por
código en `tools/generate_effect_sprites.py`, sin ningún asset
externo.

## Cómo correr el juego

```bash
.venv/bin/python main.py
```

Al arrancar se muestra la portada (`assets/graphics/ui/cover.jpg`,
`StartState`) de fondo; presionar **Enter** pasa directo al tablero.

El tablero es de 6x6 con 8 tipos de ficha (uno por elemento). El
jugador y el enemigo empiezan con 100 HP; el combate termina cuando el
HP de alguno llega a 0. Intercambiar dos fichas adyacentes que no
forman ningún match las revierte automáticamente. Si una cascada deja
el tablero sin ningún movimiento posible, se reordena solo (con aviso
en pantalla) en vez de dejar al jugador trabado.

El enemigo no juega el tablero: cada turno suyo elige un elemento al
azar y ataca. Como escalado de dificultad, el tamaño de match que
simula ese ataque crece con la duración del combate — empieza en 3
fichas (multiplicador base x1.0) y sube una ficha cada
`ENEMY_RAMP_TURNS` (3) turnos suyos, hasta el tope
`ENEMY_MAX_MATCH` (5, multiplicador x2.0, ver
`src/combat/combat_manager.py::_enemy_match_size`) — mismo tramo de
multiplicador 3/4/5+ que usa el jugador. Alargar el combate lo hace
más peligroso; resolverlo rápido con combos y Catálisis grandes lo
mantiene fácil.

### Controles

- **Click**: selecciona una ficha; un segundo click en una ficha
  adyacente intenta el intercambio.
- **Esc**: salir.
