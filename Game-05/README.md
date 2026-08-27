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

El eje central de este proyecto es el **desafío A05**: detectar los
valores repetidos de una matriz de enteros, aplicado a las líneas que
limpia la Catálisis del propio tablero.

## Estructura

```
Game-05/
├── main.py                          # punto de entrada: crea el Game y lo ejecuta
├── settings.py                       # configuración (ventana, tablero, sprites, puntaje)
├── test_find_repeated.py              # caso de prueba integrado del desafío A05
├── GUIA_A05_find_repeated.md          # guía del desafío A05 para el participante
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
    ├── algorithm.py                    # *** desafío A05: find_repeated *** (sin pygame)
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

> Detecta los valores repetidos de una línea del tablero (fila o
> columna), comparando cada ficha con las que le siguen. La línea se
> rellena inicialmente con los elementos que fue dejando el jugador
> con sus jugadas (sus swaps).
>
> **Key Concept:** Conjuntos, iteración.
> **Enfoque en la comprensión:** Filtrado de datos.

- La guía paso a paso para resolverlo, pensada para el participante
  (sin spoilear el código terminado), está en
  [`GUIA_A05_find_repeated.md`](GUIA_A05_find_repeated.md).
- La función a implementar es `src/algorithm.py::find_repeated`
  (lógica pura, sin depender del tablero).
- `Board.resolve_runs` (en `src/board/board.py`) es el punto de
  entrada pedido específicamente para el tablero: cada vez que una
  **Catálisis** (match-4+) limpia una fila o columna entera, esa línea
  de fichas (los `TileKind.value` de cada una, es decir, una matriz de
  enteros rellenada por las jugadas del jugador) se pasa por
  `find_repeated` para saber cuántos elementos **se repitieron**
  (aparecieron 2 o más veces) dentro de esa línea, y esa cantidad paga
  el bonus de **Resonancia Elemental** (`settings.RESONANCE_BONUS_PER_KIND`
  por elemento repetido, sumado en `PlayState._process_matches`, con
  un mensaje flotante "¡Resonancia x…!" sobre el tablero). Una
  Catálisis totalmente mixta (cada elemento aparece una sola vez) no
  suma nada extra; una donde algún elemento se repite dentro de la
  misma línea, sí.

## Caso de prueba integrado

```bash
.venv/bin/python test_find_repeated.py
```

No necesita ventana. Corre dos grupos de casos: `find_repeated` en
aislamiento (matrices sueltas) y `Board.resolve_runs` con una
Catálisis armada a mano (línea totalmente mixta, línea con dos
elementos repetidos, línea homogénea, y un Match-3 común sin
Catálisis) para confirmar que el bonus de resonancia se calcula bien
en cada caso.

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
