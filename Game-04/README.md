# Espejo de Códigos

Microvideojuego de una sola pantalla, hecho en Python con
[**Pygame**](https://www.pygame.org/) y el framework
[**gale**](https://pypi.org/project/gale-engine/) (manejo de estados,
ciclo del juego y entrada), con la misma arquitectura de ejemplo que el
resto de proyectos de este repositorio.

## De qué se trata

Una breve introducción, presentada como un log de consola, explica el
contexto: eres una terminal de interceptación y cada transmisión que
llega debe verificarse antes de que expire el temporizador.

En cada una de las 8 rondas llega una transmisión con una cadena de
texto. El jugador debe decidir si esa señal **conserva su patrón** al
cruzar el espejo (se lee igual en sentido inverso) o si **se altera**
(no se lee igual) — y tiene solo **4 segundos** para responder, con un
temporizador en pantalla que cuenta hacia atrás mostrando hasta los
microsegundos. Si el tiempo llega a cero antes de responder, ocurre una
explosión y el juego termina en una pantalla de Game Over.

Las 8 rondas se eligen al azar (sin repetir dentro de una misma
partida) de un banco de 32 palabras, así que las palabras concretas
cambian de una partida a otra. Al completar las 8 rondas a tiempo se
muestra una pantalla de resultados con cada palabra en **verde** (si se
acertó) o **rojo** (si no), más el tiempo total.

Evalúa comprensión de lógica de cadenas, razonamiento simbólico y
desempeño bajo presión de tiempo: la regla exacta que se aplica nunca
se explica en pantalla, el jugador debe inferirla jugando.

## Flujo de pantallas

```
StoryState  →  PlayState  →  ResultsState (si completas las 8 rondas a tiempo)
                    ↓
              GameOverState (si el temporizador de una ronda llega a 0)
```

`ResultsState` y `GameOverState` reinician con **R** yendo directo a
una `PlayState` nueva (no repiten la introducción).

## Estructura

Misma arquitectura que el resto de juegos de este repositorio (por
ejemplo `Game-01`): un `main.py` de entrada, un `settings.py` con la
configuración (ventana, fuentes, colores, atajos), y un paquete `src/`
con la clase del juego y sus pantallas (`states/`), siguiendo el patrón
Game + StateMachine + InputHandler de `gale`.

```
Game-04/
├── README.md
├── requirements.txt
├── main.py                     # punto de entrada: crea el Game y lo ejecuta
├── settings.py                 # ventana, fuentes, colores, atajos, sonidos
├── pytest.ini
├── tests/                      # pruebas automatizadas (ver más abajo)
├── assets/
│   └── sounds/
│       ├── Computer_Sound.mp3  # bucle de la introducción (ver StoryState)
│       ├── Boom.mp3            # explosión al agotarse el tiempo (ver GameOverState)
│       ├── Clock.mp3           # tictac en bucle mientras corre el temporizador (ver PlayState)
│       ├── Correct.mp3         # respuesta acertada (ver PlayState._handle_answer)
│       ├── Incorrect.mp3       # respuesta equivocada (ver PlayState._handle_answer)
│       └── Congratulations.mp3 # las 8 rondas completadas a tiempo (ver ResultsState)
└── src/
    ├── mirror_code_game.py     # clase Game: arranca el StateMachine
    ├── signal_check.py         # *** is_stable_signal *** (sin pygame ni gale)
    └── states/
        ├── story_state.py      # introducción estilo consola
        ├── play_state.py       # pantalla de juego: las 8 rondas + temporizador
        ├── game_over_state.py  # explosión + pantalla de Game Over
        └── results_state.py    # pantalla final de resultados
```

`src/signal_check.py` no importa pygame ni gale: es lógica pura sobre
un `str`, igual que `src/algorithm.py` en `Game-03`, para poder
leerla, probarla y calificarla de forma aislada de la parte gráfica.

## Requisitos

- Python 3.10 o superior.
- Un entorno con soporte gráfico (ventana de escritorio) y, para
  escuchar el sonido de la introducción, salida de audio. No requiere
  conexión a internet ni base de datos.

## Instalación de Gale

Este proyecto usa el framework **gale** (paquete `gale-engine` en PyPI),
ya usado por el resto de juegos de este repositorio (por ejemplo
`Game-01` y `Game-03`). Se instala igual que cualquier otra dependencia
de Python:

```bash
cd Game-04
python3 -m venv .venv
source .venv/bin/activate      # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

`gale-engine` instala automáticamente Pygame y el resto de sus propias
dependencias, así que no hace falta instalarlas por separado.

## Cómo ejecutar

```bash
cd Game-04
.venv/bin/python main.py
```

(o `python main.py` si ya activaste el entorno virtual con `source
.venv/bin/activate`)

## Controles

- **Clic o Enter/Espacio**: en la introducción, adelanta el texto (si
  todavía se está escribiendo) o avanza a jugar (una vez terminado).
- **Clic en un botón**: responde la ronda actual.
- **R**: reinicia una partida nueva desde la pantalla de resultados o
  desde Game Over.
- **ESC**: cierra el juego en cualquier pantalla.

## Pruebas automatizadas

Incluye una batería de pruebas con [`pytest`](https://pytest.org/), con
la misma organización que usa `Game-01` (`pytest.ini` en la raíz,
código de prueba en `tests/`): la introducción y su efecto de
escritura, el banco de palabras, el flujo completo de una partida
(rondas, temporizador, puntaje, registro), la transición a Game Over
cuando el tiempo se agota, y la pantalla de resultados.

`pytest` no es una dependencia del juego (no aparece en
`requirements.txt`), así que se instala aparte, solo si vas a correr
las pruebas:

```bash
cd Game-04
.venv/bin/python -m pip install pytest
.venv/bin/pytest -v
```

## Registro de la partida

Cada ronda respondida agrega un registro interno (`PlayState.game_log`)
con la cadena mostrada, la respuesta del jugador, la respuesta
correcta, si acertó y el tiempo de respuesta en milisegundos:

```json
{
  "round": 1,
  "string": "RADAR",
  "player_answer": "stable",
  "correct_answer": "stable",
  "is_correct": true,
  "response_time_ms": 1834
}
```

Ese registro es lo que colorea cada palabra en la pantalla de
resultados. No se imprime por consola ni se guarda o envía a ningún
servicio externo.
