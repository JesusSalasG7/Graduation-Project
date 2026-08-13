# Cubo de Rubik — simulación interactiva (Pygame + gale)

Simulación interactiva de un Cubo de Rubik 3x3x3, hecha en Python con
[**Pygame**](https://www.pygame.org/) y el framework
[**gale**](https://pypi.org/project/gale-engine/) (manejo de estados,
ciclo del juego y UI), generada con `gale-admin` y con la misma
arquitectura de ejemplo que el resto de proyectos de este repositorio.

El eje central de este proyecto es el **desafío A03**: búsqueda de un
bloque 3D pequeño dentro de una matriz 3D más grande, por fuerza
bruta, aplicado al propio estado del cubo.

## Estructura

```
cubo_rubik/
├── main.py                      # punto de entrada: crea el Game y lo ejecuta
├── settings.py                   # configuración (resolución, input)
├── test_search_3d_pattern.py      # caso de prueba integrado del desafío A03
└── src/
    ├── cubo_rubik.py             # clase Game: arranca el StateMachine
    ├── algorithm.py                # *** desafío A03: buscar_patron_3d *** (sin pygame)
    ├── rubik_cube.py               # *** lógica del cubo: matriz 3x3x3, movimientos *** (sin pygame)
    ├── vista_3d.py                  # proyección 3D del cubo (rotación, perspectiva, culling)
    └── states/
        └── play_state.py          # interfaz/animación (gale.ui + pygame)
```

`src/algorithm.py` y `src/rubik_cube.py` no importan pygame ni gale:
son lógica pura sobre listas anidadas de enteros, para poder leerlos,
probarlos y calificarlos de forma aislada de la parte gráfica (que
vive en `src/vista_3d.py` y `src/states/play_state.py`).

## Modelo del cubo

`RubikCube.matriz` es una lista de listas de listas (`matriz[x][y][z]`,
cada eje con valores 0, 1 o 2) donde cada una de las 27 celdas guarda
el **identificador entero** de la pieza física que ocupa esa posición:
`0` es el núcleo central (no es una pieza visible en un cubo real) y
`1..26` son las 26 piezas (centros, aristas y esquinas). Al aplicar un
movimiento, el identificador de cada pieza "viaja" con ella, así que
la matriz siempre refleja qué pieza está en cada posición — el estado
que necesita el desafío A03 (recorrer y comparar bloques de una matriz
3D).

En paralelo, `RubikCube.colores` modela los stickers: para cada
`(x, y, z, dirección_hacia_afuera)` donde hay una cara visible, guarda
su color (uno de los 6 oficiales, ver más abajo). A diferencia de
`matriz`, `colores` sí rota tanto de posición como de orientación al
girar una capa, así que un giro o una mezcla cambian realmente los
colores visibles, igual que en un cubo real.

Los movimientos usan la notación estándar de un cubo de Rubik:
- Capas exteriores: `U`, `D`, `L`, `R`, `F`, `B`.
- Capas interiores: `M` (Middle, entre L y R), `E` (Equator, entre D y
  U), `S` (Standing, entre F y B).
- Doble capa ("wide"): el nombre de una capa exterior seguido de `w`,
  por ejemplo `Uw` (gira esa capa junto con su interna contigua).

Todos, sentido horario por defecto; con un apóstrofe al final (por
ejemplo `U'` o `Uw'`), sentido antihorario. Internamente, cada
movimiento es el giro de una o dos capas (3x3 piezas cada una)
alrededor de un eje (`RubikCube.girar_capa`), y actualiza `matriz` y
`colores` en conjunto.

## El desafío A03

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

- La implementación exacta, comentada paso a paso, está en
  `src/algorithm.py::buscar_patron_3d` (fuerza bruta pura, sin
  depender del cubo).
- `RubikCube.search_3d_pattern(target_submatrix)` (en
  `src/rubik_cube.py`) es el punto de entrada pedido específicamente
  para el cubo: busca `target_submatrix` (por ejemplo, un bloque
  2x2x2) dentro del estado actual del cubo (`self.matriz`) usando
  `buscar_patron_3d`, y devuelve la posición `(x, y, z)` donde
  empieza la coincidencia, o `None` si no se encontró.

## Caso de prueba integrado

```bash
cd cubo_rubik
../.venv/bin/python test_search_3d_pattern.py
```

No necesita pygame ni una ventana (`rubik_cube.py` y `algorithm.py` no
lo importan). Corre 4 casos y los imprime en consola:

1. Un bloque 2x2x2 tomado de la esquina `(0,0,0)` del cubo resuelto →
   debe encontrarse ahí mismo.
2. El mismo bloque, después de mezclar el cubo con movimientos
   aleatorios → normalmente ya no se encuentra (las piezas se
   movieron).
3. Un bloque imposible (relleno con el id `99`, que ninguna pieza
   tiene) → nunca se encuentra.
4. Un bloque más grande (3x3x2) tomado de un cubo recién reiniciado →
   debe encontrarse en su posición de origen.

## Cómo correr la simulación interactiva

```bash
cd cubo_rubik
../.venv/bin/python main.py
```

El cubo se dibuja en una **proyección 3D real** (`src/vista_3d.py`):
sus 6 caras, cada una con su grilla 3x3 de "stickers" pintados con los
colores oficiales de un cubo de Rubik (blanco `#FFFFFF`, amarillo
`#FFD500`, rojo `#B71234`, naranja `#FF5800`, azul `#0046AD` y verde
`#009B48` — ver `RubikCube.colores`), rotadas en el espacio con
perspectiva simple. Como los colores viajan con cada pieza al girar
una capa, tanto los movimientos individuales como "Mezclar" cambian
realmente el aspecto del cubo, igual que uno físico. En cada cuadro se
recalculan las normales de las 6 caras, se descartan las que miran
para el otro lado ("backface culling" — por eso nunca se ven más de 3
caras a la vez, igual que en un cubo real) y las visibles se dibujan
de la más lejana a la más cercana ("algoritmo del pintor").

La pantalla solo muestra el cubo, centrado (`src/states/play_state.py`)
-- se controla enteramente con mouse y teclado, sin botones en
pantalla. Cada giro de capa por teclado se **anima** (180ms, ver
`DURACION_ANIMACION_MOVIMIENTO`): la capa gira visualmente de 0 a 90
grados (`vista_3d.AnimacionCapa`) antes de aplicarse de verdad sobre
`RubikCube` -- mientras dura, se ignoran teclas nuevas, para que nunca
haya dos giros superpuestos. Al terminar, se imprime en la consola
junto con el estado de las 6 caras (`RubikCube.imprimir_colores`,
letras W/Y/R/O/B/G).

### Controles

- **Click y arrastrar**: rota la cámara libremente en 3D (eje
  horizontal = yaw, eje vertical = pitch).
- **Flechas**: orbitan la cámara en pasos de 15° (Izquierda/Derecha =
  yaw, Arriba/Abajo = pitch) sin arrastrar el mouse.
- **U D L R F B**: giran la capa exterior correspondiente en sentido
  horario. Con **Shift** (ej. Shift+R), la giran en sentido
  antihorario ("R'"). Con **Alt** (ej. Alt+U), giran esa capa junto
  con su interna contigua -- "doble capa" o "Uw". Con **Alt+Shift**,
  doble capa en sentido antihorario ("Uw'").
- **M E S**: giran la capa interna correspondiente (M = Middle, entre
  L y R; E = Equator, entre D y U; S = Standing, entre F y B) en
  sentido horario, o antihorario con **Shift** (ej. Shift+M = "M'").
  No tienen variante de doble capa (ya son la capa del medio).
- **Esc**: salir.

Nota: no es posible que Shift dispare a la vez "doble capa" e
"invertir sentido" para la misma tecla -- son dos usos de la misma
tecla física que no pueden convivir en un solo evento. Por eso Shift
quedó reservado para invertir el sentido de giro y Alt para la doble
capa (ver el docstring de `PlayState._registrar_atajos_de_teclado`).
Se usa Alt en vez de Ctrl (usado en una versión anterior) porque Ctrl
se presta a activarse sin querer -- atajos del sistema operativo,
reflejos de teclado -- y eso se sentía como un giro de dos capas
"random" al querer girar solo una.
