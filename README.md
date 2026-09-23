# Vibe Coding — Panel Experimental

Herramienta de proyecto de grado para estudiar cómo las personas usan
IA para programar ("vibe coding"): un panel de escritorio que guía a
un participante a través de 7 minijuegos, cada uno con una función
rota que el participante debe pedirle a una IA que resuelva **sin
ver el enunciado real**, mientras se registran datos biométricos
(EEG, frecuencia cardíaca, emociones y mirada por cámara) y sus
respuestas a cuestionarios de comprensión/razonamiento.

## Índice

1. [Descripción general](#descripción-general)
2. [Estructura del proyecto](#estructura-del-proyecto)
3. [Requisitos previos](#requisitos-previos)
4. [Instalación](#instalación)
   - [1. Entorno base (panel + juegos)](#1-entorno-base-panel--juegos)
   - [2. Backend de IA (`claude` o Gemini)](#2-backend-de-ia-claude-o-gemini)
   - [3. Sensores opcionales](#3-sensores-opcionales)
5. [Cómo usar la aplicación](#cómo-usar-la-aplicación)
   - [Arrancar el panel](#arrancar-el-panel)
   - [Pestaña Juegos](#pestaña-juegos)
   - [Pestaña Participantes](#pestaña-participantes)
   - [Sesión guiada](#sesión-guiada)
   - [Pestaña Sesión: datos guardados y dataset](#pestaña-sesión-datos-guardados-y-dataset)
6. [Dónde quedan los datos](#dónde-quedan-los-datos)
7. [Solución de problemas comunes](#solución-de-problemas-comunes)

---

## Descripción general

El panel (`graphic_interface/`) es el punto de entrada de todo el
experimento. Desde ahí se puede:

- Jugar cualquiera de los 7 juegos suelto, sin sesión guiada.
- Registrar participantes (anónimos dentro de la app: "Participante
  1", "Participante 2", ...).
- Correr una **sesión guiada**: el participante recorre los 7 juegos
  en un orden fijo (de más fácil a más difícil), y en cada uno pasa
  por 6 etapas (ver más abajo) mientras se capturan, de forma
  opcional, tres fuentes de datos biométricos:
  - **NeuroSky MindWave Mobile** (EEG: atención, meditación, ondas
    cerebrales).
  - **Cámara** (emoción dominante + porcentaje por categoría vía
    DeepFace, y dirección de mirada izquierda/derecha vía MediaPipe).
  - **Reloj compatible con Samsung Health** (frecuencia cardíaca).
- Consolidar todo lo capturado en un único dataset CSV para análisis
  (`data/build_dataset.py`).

Cada uno de los 7 juegos (`Game-01` a `Game-07`) es un microvideojuego
independiente (Pygame + el framework `gale`) con una función
específica **deliberadamente rota o sin implementar**: ese es el
"desafío" que el participante debe resolver escribiéndole un prompt a
una IA aislada (sin contexto del juego ni del enunciado), para
después responder cuestionarios sobre la respuesta que le llegó.

## Estructura del proyecto

```
Graduation-Project/
├── graphic_interface/     # Panel principal (GUI, orquesta toda la sesión guiada)
│   ├── app.py             # Ventana principal: pestañas Juegos/Participantes/Sesión
│   ├── main.py            # Punto de entrada (python graphic_interface/main.py)
│   ├── session_wizard.py  # Flujo completo de la sesión guiada (Etapas 1-6)
│   ├── challenges.py      # Enunciados de los 7 desafíos de programación
│   ├── heart_rate_import.py, neurosky_launcher.py, camera_tracker_launcher.py, eye_tracker_launcher.py
│   │                      # Integración con cada dispositivo/sensor
│   ├── stage_capture.py   # Recorte y resumen de los datos por etapa
│   ├── requirements.txt
│   └── data/              # participants.json, quiz_results/, emotion_logs/ (NO va al repo)
├── Game-01/ … Game-07/    # Un juego por carpeta, cada uno con su propio .venv y requirements.txt
├── tools/                 # Scripts de captura de sensores (NeuroSky, cámara, reloj)
│   ├── camera_tracker.py  # Emotion Tracker + Eye Tracker fusionados (usado por la sesión guiada)
│   ├── eye_tracker.py, emotion_tracker.py  # Versiones sueltas (debug/desarrollo manual)
│   ├── NeuroSky/          # Driver (NeuroPy.py), script de prueba y guía del dispositivo
│   └── requirements.txt   # Instrucciones DETALLADAS de instalación de estos sensores
├── data/
│   └── build_dataset.py   # Genera el CSV consolidado de todas las sesiones exportadas
└── .venv/                 # Entorno virtual único compartido por el panel y los 7 juegos
```

Los datos de cada sesión (CSV, respuestas, prompts) **no se guardan
dentro del repositorio**: se escriben en el Escritorio del usuario
(`~/Escritorio/Sesiones_participantes/`), separados de cualquier dato
personal (`~/Escritorio/Participantes/`). Ver [Dónde quedan los
datos](#dónde-quedan-los-datos).

## Requisitos previos

- **Linux** (probado en Ubuntu/Debian; las instrucciones de Bluetooth
  usan `rfcomm`/`bluetoothctl`). El NeuroSky también tiene instrucciones
  para Windows en `tools/NeuroSky/GUIA_NEUROSKY.md`, pero el resto del
  proyecto no está probado ahí.
- **Python 3.12** (o razonablemente cercano — el proyecto usa
  anotaciones de tipo modernas como `list[str]`, que requieren 3.9+).
- **Un backend de IA** para la Etapa 3 de la sesión guiada (respuesta
  aislada de la IA) y la generación de los cuestionarios de
  comprensión/razonamiento — configurable con la variable de entorno
  `AI_PROVIDER` (ver `graphic_interface/ai_backend.py`):
  - `AI_PROVIDER=claude` (default, o simplemente no definir la
    variable): **[Claude Code](https://claude.com/claude-code)**
    instalado y con sesión iniciada (`claude` en el `PATH`). No hace
    falta una `ANTHROPIC_API_KEY` propia — usa la sesión/suscripción
    que ya tengas configurada en el CLI.
  - `AI_PROVIDER=gemini`: una **API key de [Google AI
    Studio](https://aistudio.google.com/apikey)** en la variable de
    entorno `GEMINI_API_KEY`. Opcionalmente `GEMINI_MODEL` para
    cambiar el modelo (default `gemini-3.6-flash`). No requiere
    Claude Code ni ningún paquete extra — habla por REST con
    `requests` (ya en `graphic_interface/requirements.txt`).
- **Hardware opcional** (la app funciona sin ninguno de estos —
  simplemente se destildan en el modal de dispositivos de la sesión):
  - Diadema NeuroSky MindWave Mobile (Bluetooth).
  - Webcam.
  - Un reloj/smartband que exporte a Samsung Health (Samsung Galaxy
    Watch u otro compatible).

## Instalación

### 1. Entorno base (panel + juegos)

Parado en la raíz del repositorio:

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r graphic_interface/requirements.txt
.venv/bin/pip install $(find Game-* -maxdepth 1 -name requirements.txt -exec cat {} \; | grep -v '^#' | sort -u)
```

Ese segundo `pip install` es exactamente lo que hace el botón
**"🛠️ Reparar entorno"** de la pestaña Juegos del panel (más el propio
`graphic_interface/requirements.txt`): podés instalar todo a mano una
vez con los comandos de arriba, y después usar ese botón cada vez que
agregues un juego nuevo o cambie alguna versión, en vez de repetir el
proceso manual.

> ⚠️ El botón "Reparar entorno" **no** instala las dependencias de
> `tools/` (cámara/NeuroSky) — esas requieren pasos manuales
> especiales, ver la sección 3 de más abajo. No corras
> `pip install -r tools/requirements.txt` a secas: instalaría a la vez
> dos paquetes de OpenCV incompatibles entre sí (ver el comentario al
> principio de ese archivo).

Con el entorno instalado, arrancá el panel:

```bash
.venv/bin/python graphic_interface/main.py
```

### 2. Backend de IA (`claude` o Gemini)

Ambos usos (respuesta "aislada" de la Etapa 3 en
`graphic_interface/isolated_prompt.py`, y los bancos de preguntas de
comprensión/razonamiento + explicación de la Etapa 5 en
`graphic_interface/challenge_solver.py`) pasan por el mismo selector
configurable en `graphic_interface/ai_backend.py`.

**Opción A — CLI `claude` (default):**

Instalá Claude Code siguiendo la [documentación
oficial](https://docs.claude.com/claude-code) e iniciá sesión una vez
(`claude` sin argumentos, o `claude login`). El proyecto lo invoca en
modo headless (`claude -p ...`). No hace falta definir `AI_PROVIDER` —
es el comportamiento si esa variable no está seteada.

**Opción B — API de Gemini:**

No requiere Claude Code instalado ni ningún paquete extra (usa
`requests`, ya en `graphic_interface/requirements.txt`).

1. **Conseguí una API key** en [Google AI
   Studio](https://aistudio.google.com/apikey):
   - Entrá con una cuenta de Google (cualquiera sirve, no hace falta
     que sea la del proyecto).
   - Click en **"Create API key"** ("Crear clave de API").
   - Si te pide elegir/crear un proyecto de Google Cloud, dejá que lo
     genere automático — no hace falta configurar nada ahí.
   - Copiá la key que te muestra (empieza con algo como `AIza...`).
     Tiene un nivel gratuito con límite de requests por minuto/día,
     suficiente para pruebas, sin necesidad de tarjeta de crédito.

2. **Exportá las variables** en la terminal desde la que vas a
   arrancar el panel:

   ```bash
   export AI_PROVIDER=gemini
   export GEMINI_API_KEY="tu-api-key"
   # opcional, default gemini-3.6-flash:
   export GEMINI_MODEL="gemini-3.6-flash"
   ```

   Esto solo dura mientras esa terminal esté abierta. Para no tener
   que repetirlo cada vez, agregá esas mismas líneas al final de tu
   `~/.bashrc` (o `~/.zshrc` si usás zsh) y abrí una terminal nueva.

3. **Verificá la conexión** antes de correr una sesión real:

   ```bash
   .venv/bin/python graphic_interface/test_gemini_connection.py
   ```

   Si imprime `Conexión OK. Respuesta del modelo: 'OK'`, quedó bien
   configurado. Si falla, el mensaje de error indica la causa (key
   inválida, modelo no disponible, etc.).

4. **Arrancá el panel** con esas variables ya exportadas en la misma
   terminal (`.venv/bin/python graphic_interface/main.py`) y fijate
   en el indicador **"IA: Gemini"** de la barra lateral (abajo a la
   izquierda) — si aparece con ✅ está todo listo; con ⚠️ falta algo
   (revisá el mensaje que muestra la app al entrar a la sesión
   guiada).

> 🔒 **Nunca compartas tu `GEMINI_API_KEY`** (por chat, en un commit,
> en un issue, etc.) — cualquiera que la tenga puede usarla a tu
> nombre. Si por error quedó expuesta en algún lado, revocala en
> [Google AI Studio](https://aistudio.google.com/apikey) y generá una
> nueva. El proyecto no la guarda en ningún archivo: siempre se lee
> desde la variable de entorno en el momento de cada llamada (ver
> `graphic_interface/ai_backend.py`).

---

Si el backend seleccionado no está disponible (CLI `claude` fuera del
`PATH`, o `AI_PROVIDER=gemini` sin `GEMINI_API_KEY`), la app lo detecta
solo (`ai_backend.provider_available`) y te avisa **antes** de arrancar
la sesión guiada, con la opción de seguir de todas formas — útil si
alguien solo quiere probar la interfaz, los juegos o los sensores sin
tener ningún backend de IA configurado. Si igual continuás sin él, las
Etapas 3, 4 y 5 muestran un error explicando que no se pudo invocar la
IA, en vez de romper la sesión.

### 3. Sensores opcionales

Cada sensor es completamente opcional (se puede destildar en el modal
de "¿Qué dispositivos vas a usar en esta sesión?"), y cada uno tiene
su propia receta de instalación. **No las mezcles**: cámara y
NeuroSky usan entornos distintos a propósito, porque sus dependencias
(OpenCV con y sin extras, TensorFlow, MediaPipe) se pisan entre sí si
conviven en el mismo `.venv`.

#### NeuroSky (diadema EEG)

Usa el `.venv` unificado de la raíz (ya instalado en el paso 1) — solo
falta emparejar el dispositivo por Bluetooth:

```bash
# Una sola vez: permiso para usar puertos seriales
sudo usermod -a -G dialout $USER   # cerrar sesión y volver a entrar después de esto

# Emparejar (buscá "MindWave Mobile" en tu gestor de Bluetooth, PIN 0000 o 1234)
# y anotá su MAC, luego:
sudo rfcomm bind /dev/rfcomm0 <MAC_DEL_DISPOSITIVO> 1
sudo chmod 666 /dev/rfcomm0
```

Guía completa (colocación del sensor, interpretación de la calidad de
señal, instrucciones para Windows) en `tools/NeuroSky/GUIA_NEUROSKY.md`.
Desde el panel, la pantalla de configuración de la sesión guiada
puede pedir la contraseña de `sudo` para hacer el `rfcomm bind` por
vos (nunca la pasa por línea de comandos, solo por stdin).

#### Cámara (emoción + mirada)

Vive en su **propio entorno virtual**, `tools/.venv-tracker`, porque
mezcla `mediapipe` (necesita `opencv-contrib-python`) y `deepface`
(necesita `opencv-python`) — instalar ambos paquetes de OpenCV juntos
rompe `cv2` (confirmado: pisa los archivos de `cv2/data/`). La receta
exacta (con las banderas `--no-deps` necesarias) está documentada en
`tools/requirements.txt`, sección 3:

```bash
python3 -m venv tools/.venv-tracker
tools/.venv-tracker/bin/pip install opencv-contrib-python==4.10.0.84 mediapipe==1.0.1
tools/.venv-tracker/bin/pip install --no-deps deepface==0.0.93 retina-face
tools/.venv-tracker/bin/pip install fire Flask flask-cors gdown gunicorn keras mtcnn numpy pandas==2.2.2 Pillow requests tensorflow==2.21.0 tf-keras==2.21.0 tqdm
```

Para calibrar la dirección de mirada antes de la primera sesión con
una webcam nueva:

```bash
tools/.venv-tracker/bin/python tools/camera_tracker.py --calibrate
```

(el panel también ofrece calibrar desde la pantalla "Evaluador:
Configurar Cámara" de la sesión guiada, sin usar la terminal).

#### Reloj (frecuencia cardíaca)

No requiere instalar nada: es un **export manual** de Samsung Health
("Descargar mis datos personales" desde la app del teléfono), que se
arrastra y suelta (o se selecciona con el explorador de archivos) en
la pantalla "Importar reloj" de la sesión guiada. Arrastrar y soltar
necesita `tkinterdnd2` (ya instalado en el paso 1); si por algún
motivo no se puede registrar en tu sistema, la pantalla cae sola al
botón "Seleccionar archivo".

Para volver a procesar la frecuencia cardíaca de un desafío ya
cerrado (por ejemplo, si el evaluador consiguió el export después de
terminar la sesión), hay un CLI dedicado:

```bash
.venv/bin/python graphic_interface/reimport_heart_rate.py \
    --participante 1 --desafio 1 --carpeta "/ruta/al/export/samsunghealth_usuario_<fecha>"
```

## Cómo usar la aplicación

### Arrancar el panel

```bash
.venv/bin/python graphic_interface/main.py
```

La ventana arranca maximizada, con tres pestañas en la barra lateral:
**Juegos**, **Participantes** y **Sesión**.

### Pestaña Juegos

Lista todos los `Game-*` detectados automáticamente (no hace falta
registrarlos en ningún lado, alcanza con que la carpeta tenga un
`main.py`). Desde acá podés:

- **▶ Jugar**: abre el juego suelto, en pantalla completa, tal como
  está en el repositorio (sin pasar por la sesión guiada).
- **📊 Ver juegos en dificultad**: reordena la lista de más fácil a
  más difícil (mismo orden que usa la sesión guiada).
- **🛠️ Reparar entorno**: reinstala en `.venv` las dependencias del
  panel + de todos los juegos (ver [Instalación](#1-entorno-base-panel--juegos));
  útil después de un `git pull` que haya cambiado algún
  `requirements.txt`.
- **🔄 Actualizar**: vuelve a escanear la carpeta del proyecto por si
  agregaste un `Game-*` nuevo.

### Pestaña Participantes

Cada participante es **anónimo dentro de la app** ("Participante 1",
"Participante 2", ...). Al agregar uno nuevo se pide:

- **Nombre y apellido**: se guardan aparte, en
  `~/Escritorio/Participantes/participantes.csv` — nunca junto a los
  datos de la sesión (emociones, frecuencia cardíaca, etc.), a
  propósito, para no mezclar datos personales con datos anónimos de
  investigación.
- **Nivel de experiencia**: Avanzado / Intermedio / Principiante.

Hacé clic en una fila de la tabla para marcarlo como el participante
**activo** — la sesión guiada y la pestaña Sesión siempre operan
sobre ese participante activo.

### Sesión guiada

Con un participante activo, tocá **"🚀 Iniciar sesión guiada"** (en la
pestaña Sesión). El flujo es:

1. **Modal de dispositivos**: elegí qué vas a usar esta vez (reloj,
   NeuroSky, cámara) — todos tildados por defecto. Destildar uno no
   rompe nada, la sesión sigue funcionando sin pedir ni procesar los
   datos de ese dispositivo.
2. **Pantallas de configuración** (una por cada dispositivo
   habilitado, en este orden): reloj (checklist para el evaluador:
   medición continua activada, notificaciones apagadas), NeuroSky
   (emparejamiento + lecturas en vivo en una ventana aparte), cámara
   (calibración izquierda/derecha + seguimiento en vivo).
3. **Bienvenida**, y después, para cada uno de los 7 juegos (en orden
   de dificultad creciente), 6 etapas:
   - **Etapa 1 — Ver el juego roto**: el participante juega la
     versión SIN el desafío resuelto, para notar el comportamiento
     raro por su cuenta.
   - **Etapa 2 — El problema**: lee el enunciado real del desafío y
     responde un cuestionario de comprensión.
   - **Etapa 3 — Tu prompt**: escribe, a ciegas (sin ver el enunciado
     ni el juego), el prompt que le daría a una IA para resolverlo.
   - **Etapa 4 — Resultado**: ve la respuesta de esa IA aislada y
     responde un cuestionario sobre qué dice/hace esa respuesta.
   - **Etapa 5 — Razonamiento**: lee una explicación de por qué la IA
     llegó a esa respuesta y responde un segundo cuestionario.
   - **Etapa 6 — Ver la solución en acción**: juega el juego con el
     código de la IA ya aplicado.
   - Desde acá puede "Reintentar este desafío" (vuelve a la Etapa 3),
     seguir al "Siguiente juego" (sin cortar los sensores en vivo), o
     — en el último desafío — "Terminar sesión guiada" (ahí sí pide
     el export del reloj, ver [Reloj](#reloj-frecuencia-cardíaca)).
   - **"💾 Guardar progreso"** corta la sesión a mitad de camino;
     al volver a entrar, retoma en el siguiente desafío pendiente.

Presionar ESC durante cualquier minijuego lanzado desde la sesión
guiada lo cierra y vuelve al panel.

### Pestaña Sesión: datos guardados y dataset

Con un participante activo, esta pestaña muestra:

- **📊 Datos guardados**: una matriz de lo que ya se exportó (por
  etapa) para el desafío que elijas, del participante activo —
  NeuroSky, emoción, mirada, frecuencia cardíaca (con su promedio en
  bpm), resultado del cuestionario, aperturas del enunciado. Se lee
  siempre de disco, así que refleja el estado real aunque hayas
  reiniciado la app.
- **🧬 Dataset consolidado**: el botón **"🔄 Generar / actualizar
  dataset"** corre `data/build_dataset.py` sobre TODOS los
  participantes/desafíos ya exportados y arma un único CSV (una fila
  por etapa de cada desafío, con las lecturas crudas de cada sensor).
  Una vez generado, **"🖥️ Ver dataset completo"** lo abre en una
  ventana aparte a pantalla completa para poder revisarlo con
  detalle.

## Dónde quedan los datos

| Qué | Dónde |
|---|---|
| Datos de cada sesión (sensores, cuestionarios, prompts) | `~/Escritorio/Sesiones_participantes/<Nombre_Apellido_N>/Desafio_N/Etapa_N/...` |
| Nombre/apellido de los participantes (dato personal) | `~/Escritorio/Participantes/participantes.csv` |
| Registro anónimo de participantes de la app | `graphic_interface/data/participants.json` (ignorado por git) |
| Respuestas de cuestionarios | `graphic_interface/data/quiz_results/PARTICIPANTE_N.json` (ignorado por git) |
| Dataset consolidado | `data/dataset_sesiones.csv` (se regenera con el botón de la app o `python data/build_dataset.py`; ignorado por git) |

Nada de lo anterior se sube al repositorio (ver `.gitignore`): son
datos de participantes reales, algunos con información sensible
(biométrica o personal).

## Solución de problemas comunes

- **"Falta la librería 'pyserial'" al conectar NeuroSky**: corré
  `.venv/bin/pip install pyserial` (ya está en
  `graphic_interface/requirements.txt`, así que "Reparar entorno"
  también lo soluciona).
- **La cámara no abre / "cap.isOpened() da False"**: solo un proceso
  puede tener la webcam abierta a la vez. Cerrá cualquier otra
  instancia de `camera_tracker.py`/`eye_tracker.py`/
  `emotion_tracker.py` que haya quedado corriendo.
- **Import de `cv2` roto después de instalar algo en
  `tools/.venv-tracker`**: significa que se instaló `opencv-python`
  además de `opencv-contrib-python` en ese venv. Borrá el venv y
  rehacé la receta de la sección
  [Cámara](#cámara-emoción--mirada) tal cual, en ese orden.
- **Las Etapas 3/5 muestran "no se pudo generar" o timeout**: el CLI
  `claude` no respondió a tiempo o no está en el `PATH`. Confirmá
  `claude --version` desde la misma terminal donde corre el panel.
- **El reloj no tiene lecturas dentro de la ventana exacta de una
  etapa**: es esperable si no tenías "Medición continua" activada —
  el reloj solo mide cada varios minutos. El sistema usa la lectura
  más cercana (marcada como aproximada) en vez de dejar la etapa sin
  dato; ver la columna de advertencias del dataset consolidado.
