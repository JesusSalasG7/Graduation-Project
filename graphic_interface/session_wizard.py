"""Modulo de "sesion guiada": reemplaza toda la interfaz por un asistente de
6 etapas para el participante activo, empezando por el juego mas facil.

Etapa 1 -- se lanza una copia temporal del juego TAL CUAL esta en el repo
           -- la funcion/metodo del desafio ya queda sin resolver ahi
           (TODO + raise NotImplementedError, ver CHALLENGES en
           challenges.py) -- para que el participante vea en vivo la
           falla real ANTES de leer el enunciado (ver game_patch.
           launch_game_without_solution). Nunca se toca el codigo fuente
           real del proyecto.
Etapa 2 -- pantalla dividida: enunciado completo del desafio a la izquierda,
           7 preguntas de opcion multiple sobre ESE enunciado a la derecha
           (banco estatico, ver statement_quiz.py).
Etapa 3 -- el participante escribe su propio prompt para resolverlo; al
           enviarlo, ese prompt -- y SOLO ese prompt, sin el enunciado ni
           ningun otro contexto -- se envia a una IA completamente aislada
           (ver isolated_prompt.py y challenge_solver.generate_isolated_
           response): si el prompt no alcanza a describir el problema, la
           respuesta lo va a reflejar.
Etapa 4 -- pantalla dividida: la respuesta cruda que devolvio esa IA
           aislada a la izquierda, 7 preguntas de opcion multiple sobre esa
           respuesta concreta a la derecha (generadas dinamicamente).
Etapa 5 -- pantalla dividida: a la izquierda, la misma respuesta de la
           Etapa 4 junto con una evaluacion generada por IA de si el
           razonamiento y la implementacion son correctos y alcanzan para
           resolver el desafio; a la derecha, 7 preguntas de opcion
           multiple sobre esa evaluacion (generadas
           junto con las de la Etapa 4 y la explicacion, ver
           challenge_solver.generate_response_quiz).
Etapa 6 -- se lanza otra copia temporal del juego, esta vez con la funcion/
           metodo del desafio reemplazada por el codigo EXACTO que genero
           la IA aislada en la Etapa 3-4, para observar esa solucion
           concreta en accion (ver game_patch.launch_game_with_solution).

Las respuestas de los 3 cuestionarios se guardan por participante (ver
quiz_results.py). Hay que responder las 7 preguntas para poder avanzar,
pero no se exige acertarlas -- son un registro, no un examen con nota de
corte.

Al terminar un desafio se puede pasar al siguiente (en orden de
dificultad), o guardar el progreso y salir: la proxima vez que este
participante entre a la sesion guiada, retoma en el desafio siguiente
en lugar de volver a empezar desde el primero.
"""

import signal
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from tkinter import messagebox
from typing import Optional

import customtkinter as ctk

from camera_tracker_launcher import delete_camera_data, run_calibration, start_camera_tracker
from challenge_solver import GUIDED_SESSION_GAME_ORDER, ChallengeSolveResult, generate_isolated_response
from challenges import get_challenge
from eye_tracker_launcher import eye_log_file
from game_launcher import discover_games, emotion_log_file
from game_patch import launch_game_with_solution, launch_game_without_solution
from heart_rate_import import HeartRateDropFrame, import_heart_rate_for_challenge
from neurosky_launcher import (
    NEUROSKY_DATA_FILE,
    RFCOMM_DEVICE,
    bind_neurosky,
    delete_neurosky_data,
    release_neurosky,
    start_neurosky_test,
    sudo_needs_password,
)
from participant_store import participant_label
from personal_records import load_personal_record
from quiz import QuizQuestion
from quiz_results import save_quiz_answers
from stage_capture import (
    StageTimer,
    available_challenges,
    challenge_dir,
    participant_session_dir,
    slice_emotion,
    slice_eye,
    slice_neurosky,
    source_info,
    stage_dir,
    write_challenge_manifest,
    write_cuestionario_txt,
    write_session_index,
    write_stage3_files,
    write_stage_sensor_files,
    write_sync_timeline,
)
from statement_view import render_statement
from statement_quiz import get_statement_questions

FONT_FAMILY = "Segoe UI"
PROGRESS_ATTRIBUTE = "sesion_guiada_siguiente_juego"

# Dispositivos que la sesion guiada puede usar -- el evaluador elige
# cuales de estos van en cada sesion en el modal previo (ver
# App._ask_session_devices), y SessionWizard.start() recibe esa
# seleccion. El orden importa: es el orden en que aparecen sus pantallas
# de configuracion (ver _show_next_setup_screen).
ALL_DEVICES = ("heart_rate", "neurosky", "camera")

# El script imprime una linea por segundo mientras hay datos (ver
# test_neurosky.py); si pasan mas de esto sin ninguna linea nueva, algo se
# colgo (el dispositivo se desconecto, perdio bateria, etc.) -- ver
# _neurosky_watchdog_tick.
NEUROSKY_STALE_SECONDS = 8

# Toda la tipografia de la sesion guiada se agranda respecto al resto de
# la app (pedido explicito: mejor legibilidad durante la sesion). 1.5x,
# luego +50% (2.25x), luego -15% sobre eso -> 1.9125x en total.
FONT_SCALE = 1.9125


def scaled(size: int) -> int:
    return round(size * FONT_SCALE)


# Los anchos de wrapeo de texto crecen mas suave que la letra (60% del
# aumento) -- si crecieran al mismo ritmo que la fuente, la columna
# necesitaria ser mas ancha que la pantalla disponible.
WRAP_SCALE = 1 + (FONT_SCALE - 1) * 0.6


def wrap(px: int) -> int:
    return round(px * WRAP_SCALE)


class SessionWizard:
    def __init__(self, container: ctk.CTkFrame, app, colors: dict):
        self.container = container
        self.app = app
        self.c = colors
        self.game_index = 0
        self.current_game = None
        self.current_challenge = None
        self.current_result: ChallengeSolveResult | None = None
        self.stage1_answers: dict[int, ctk.IntVar] = {}
        self.stage3_answers: dict[int, ctk.IntVar] = {}
        self.stage4_answers: dict[int, ctk.IntVar] = {}
        self._neurosky_process: Optional[subprocess.Popen] = None
        # Ventana aparte ("Datos del Neurosky") con el estado, las lecturas
        # en vivo y su propio boton de reconexion -- NO es hija de
        # self.container, asi que _clear() no la destruye al cambiar de
        # pantalla: queda abierta (y utilizable) durante toda la sesion,
        # no solo mientras se esta en la pantalla de configuracion.
        self._neurosky_window: Optional[ctk.CTkToplevel] = None
        self._neurosky_terminal: Optional[ctk.CTkTextbox] = None
        self._neurosky_status_label: Optional[ctk.CTkLabel] = None
        self._neurosky_retry_button: Optional[ctk.CTkButton] = None
        # Marca de tiempo (time.monotonic()) de la ultima linea recibida
        # del proceso -- si pasa demasiado sin ninguna, el watchdog asume
        # que se colgo (ver _neurosky_watchdog_tick / NEUROSKY_STALE_SECONDS).
        self._neurosky_last_data_at: Optional[float] = None
        # Evita disparar dos vinculaciones/lanzamientos en paralelo si se
        # llega a apretar "Reconectar" mas de una vez antes de que el
        # boton alcance a ocultarse (ver _start_neurosky_setup_thread).
        self._neurosky_setup_running = False
        # True solo si se completaron los 7 desafios de la sesion guiada
        # (ver _advance_or_finish) -- si se sale antes (por cualquier boton
        # "Salir de la sesión guiada", o cerrando la app de golpe), la
        # sesion se considera incompleta y se borran los datos del Neurosky
        # capturados hasta ese punto (ver _cleanup_neurosky_interactive /
        # cleanup_incomplete_session).
        self._session_completed = False
        # Ventana aparte con el enunciado del desafio actual, para
        # consultarlo mientras se escribe el prompt en la Etapa 3 (ver
        # _show_stage3 / _toggle_statement_window). Igual que la del
        # Neurosky, NO es hija de self.container, asi que _clear() no la
        # toca -- se cierra a mano al avanzar a la Etapa 4 o al salir.
        self._statement_window: Optional[ctk.CTkToplevel] = None

        # Camera Tracker (Emotion Tracker + Eye Tracker fusionados en un
        # solo proceso, ver tools/camera_tracker.py): se calibra/verifica
        # despues del Neurosky y antes de la Bienvenida (ver
        # _show_configure_camera_tracker), y queda corriendo en segundo
        # plano durante toda la sesion, igual que el Neurosky -- se para
        # en _exit_guided_session / cleanup_incomplete_session.
        self._camera_process: Optional[subprocess.Popen] = None
        # (left_x, right_x) que devolvio la calibracion para este
        # participante (ver camera_tracker_launcher.run_calibration) --
        # None hasta que la calibracion termina con exito.
        self._camera_calibration: Optional[tuple[float, float]] = None
        self._camera_setup_running = False
        # Referencias a los widgets de la ventana "Datos de la Cámara"
        # (NO son hijos de self.container, igual que la ventana del
        # Neurosky) -- se acceden desde hilos de fondo via self.app.after,
        # asi que pueden quedar apuntando a un widget ya destruido si la
        # ventana se cierra a mano; cada actualizacion lo maneja con un
        # try/except que limpia la referencia (mismo patron que
        # _log_neurosky/_set_neurosky_status). self._camera_continue_button
        # SI es hijo de self.container (vive en la pantalla, no en la
        # ventana aparte).
        self._camera_window: Optional[ctk.CTkToplevel] = None
        self._camera_terminal: Optional[ctk.CTkTextbox] = None
        self._camera_status_label: Optional[ctk.CTkLabel] = None
        self._camera_calibrate_button: Optional[ctk.CTkButton] = None
        self._camera_continue_button: Optional[ctk.CTkButton] = None

        # Corte por etapa (ver stage_capture.py): cronometro de inicio/fin
        # de cada etapa, para recortar por rango de tiempo los CSV
        # continuos de NeuroSky/Emotion/Eye al exportar. `_attempt_number`
        # versiona las etapas 3/4/5 cuando el participante usa "Reintentar
        # este desafío" (vuelve a la Etapa 3) -- se reinicia en
        # _start_current_game.
        self._stage_timer = StageTimer()
        self._attempt_number = 1
        # Desafios ya jugados (Etapa 5 terminada) a los que todavia no se
        # les recorto la frecuencia cardiaca -- self._stage_timer solo
        # guarda UNA ventana por numero de etapa (se pisa al empezar el
        # siguiente desafio, ver StageTimer), y la pantalla de importar el
        # reloj (ver _show_heart_rate_import) NO aparece despues de cada
        # desafio ("Siguiente juego" sigue de largo sin cortar los
        # sensores) sino recien en "Guardar progreso"/"Terminar sesion".
        # Sin este snapshot, un solo export del reloj entregado al final de
        # una sesion de varios desafios solo alcanzaba a recortarle la
        # frecuencia cardiaca al ULTIMO (ver _snapshot_pending_heart_rate /
        # _finish_challenge).
        self._pending_heart_rate_challenges: list[dict] = []
        # Aperturas del enunciado durante la Etapa 3 (ver
        # _toggle_statement_window/_close_statement_window), para el
        # registro de cuantas veces se abre y cuanto dura cada apertura.
        self._statement_log: list[dict] = []
        # Advertencias de la ultima exportacion por etapa (sensor sin
        # señal, etc.) -- se muestran como banner inline en la pantalla
        # siguiente (ver _render_pending_warnings), nunca con un
        # messagebox que trabe el avance del participante.
        self._stage_warnings: dict[int, list[str]] = {}
        # Dispositivos elegidos para esta sesion (ver ALL_DEVICES /
        # App._ask_session_devices) -- start() lo sobreescribe con lo que
        # elija el evaluador; el default de todos habilitados es solo un
        # respaldo por si algo llegara a llamar start() sin pasarlo.
        self._enabled_devices: set[str] = set(ALL_DEVICES)

    # ---------------- utilidades ----------------
    def _clear(self):
        for child in self.container.winfo_children():
            child.destroy()

    def _header(self, parent, step_text: str, title: str):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=36, pady=(30, 4))
        ctk.CTkLabel(
            row, text=step_text, font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12), weight="bold"),
            text_color=self.c["ACCENT"],
        ).pack(anchor="w")
        ctk.CTkLabel(
            row, text=title, font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(22), weight="bold"),
        ).pack(anchor="w", pady=(2, 0))

    def _exit_button(self, parent):
        ctk.CTkButton(
            parent, text="✕  Salir de la sesión guiada", width=scaled(200), height=scaled(32), corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(11)),
            fg_color="transparent", hover_color=self.c["BORDER"], border_width=1,
            border_color=self.c["BORDER"], text_color=self.c["TEXT_MUTED"],
            command=self._exit_guided_session,
        ).place(relx=1.0, rely=0.0, anchor="ne", x=-20, y=18)

    def _exit_guided_session(self):
        """Sale de la sesion guiada desde cualquier pantalla. La limpieza
        del Neurosky (parar el proceso, borrar los datos si la sesion
        quedo incompleta, y liberar el rfcomm) se dispara en un hilo de
        fondo -- puede necesitar pedir la contraseña de sudo por una
        ventana modal, asi que no puede correr en el hilo principal (ver
        _cleanup_neurosky_interactive) -- para no trabar la salida.
        """
        self._close_statement_window()
        delete_data = not self._session_completed
        neurosky_active = self._neurosky_process is not None or self._neurosky_window is not None
        camera_active = self._camera_process is not None or self._camera_window is not None
        self.app.exit_session_wizard()
        if neurosky_active:
            threading.Thread(
                target=self._cleanup_neurosky_interactive, args=(delete_data,), daemon=True,
            ).start()
        # El Camera Tracker se limpia en un hilo aparte, sin tocar el
        # flujo del Neurosky de arriba: para el proceso, borra sus CSV
        # (emocion + mirada) si la sesion quedo incompleta (esos datos de
        # una sesion abandonada no sirven para el analisis, mismo
        # criterio que el Neurosky) y cierra la ventana "Datos de la
        # Cámara".
        if camera_active:
            threading.Thread(
                target=self._cleanup_camera_interactive, args=(delete_data,), daemon=True,
            ).start()

    def _cleanup_neurosky_interactive(self, delete_data: bool):
        """Corre en un hilo de fondo (ver _exit_guided_session): para el
        proceso de test_neurosky.py, borra el CSV capturado si la sesion
        quedo incompleta, y libera el rfcomm (pidiendo la contraseña de
        sudo por una ventana modal si hace falta)."""
        self._stop_neurosky_process()

        if delete_data:
            self._log_neurosky("[INFO] Sesión incompleta -- se elimina la información capturada.")
            delete_neurosky_data()

        self._log_neurosky("[INFO] Desvinculando el NeuroSky (rfcomm release)...")
        password = None
        if sudo_needs_password():
            password = self._ask_sudo_password_blocking()
        if release_neurosky(self._log_neurosky, password=password):
            self._log_neurosky(f"[OK] {RFCOMM_DEVICE} liberado.")
        else:
            self._log_neurosky("[AVISO] No se pudo liberar el rfcomm -- puedes hacerlo a mano después.")
        self._close_neurosky_window()

    def _cleanup_camera_interactive(self, delete_data: bool):
        """Corre en un hilo de fondo (ver _exit_guided_session): para el
        Camera Tracker (Emotion + Eye fusionados), borra sus CSV (emocion
        + mirada) si la sesion quedo incompleta, y cierra la ventana
        "Datos de la Cámara"."""
        self._stop_camera_process()
        if delete_data:
            delete_camera_data(self.app.store.get_active())
        self._close_camera_window()

    def cleanup_incomplete_session(self):
        """Se llama desde App._on_close cuando la ventana se cierra de
        golpe: si hay una sesion de Neurosky activa, para el proceso, borra
        los datos capturados (una sesion interrumpida asi SIEMPRE quedo
        incompleta) e intenta liberar el rfcomm -- sin pedir contraseña por
        una ventana modal (la app se esta cerrando, no hay tiempo/sentido
        de trabar el cierre esperando eso). Si sudo no tiene una credencial
        cacheada, la liberacion simplemente no se hace: no es grave, el
        proximo `rfcomm bind` la detecta ya vinculada y no repite el paso.
        Corre sincronico (nada de esto necesita el hilo de Tk ni tarda mas
        de un par de segundos) para garantizar que termine antes de que
        App.destroy() se lleve puesta la ventana.
        """
        if self._camera_process is not None or self._camera_window is not None:
            self._stop_camera_process()
            delete_camera_data(self.app.store.get_active())
            self._close_camera_window()
        if self._neurosky_process is None and self._neurosky_window is None:
            return
        self._stop_neurosky_process()
        delete_neurosky_data()
        release_neurosky(lambda _line: None)

    def _section(self, parent, title: str):
        ctk.CTkLabel(
            parent, text=title, font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(14), weight="bold"),
        ).pack(anchor="w", pady=(0, 6))

    def _code_block(self, parent, text: str):
        card = ctk.CTkFrame(parent, fg_color=self.c["BG_CARD_ALT"], corner_radius=8)
        card.pack(anchor="w", fill="x", pady=(0, 18))
        ctk.CTkLabel(
            card, text=text, font=ctk.CTkFont(family="monospace", size=scaled(12)),
            justify="left", anchor="w",
        ).pack(anchor="w", fill="x", padx=14, pady=10)

    def _play_button(self, parent, label: str, launch_fn):
        """Boton que corre `launch_fn()` (sin argumentos, ver game_patch.py)
        en un hilo de fondo -- copiar el juego y arrancar el proceso puede
        tardar un instante -- y muestra el resultado en una etiqueta de
        estado debajo, sin bloquear la interfaz ni forzar al participante a
        esperar a que cierre la ventana del juego para poder continuar.
        """
        status_label = ctk.CTkLabel(
            parent, text="", font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12)),
            text_color=self.c["TEXT_MUTED"], wraplength=wrap(700), justify="left",
        )

        def on_click():
            button.configure(state="disabled", text="Lanzando el juego...")
            status_label.configure(text="", text_color=self.c["TEXT_MUTED"])

            def run():
                try:
                    launch_fn()
                except Exception as exc:
                    message, color = f"⚠️  No se pudo lanzar el juego: {exc}", self.c["WARNING"]
                else:
                    message, color = (
                        "🎮  Juego lanzado en una ventana aparte. Cerrala cuando termines de probarlo.",
                        self.c["TEXT_MUTED"],
                    )

                def update():
                    status_label.configure(text=message, text_color=color)
                    button.configure(state="normal", text=label)

                self.app.after(0, update)

            threading.Thread(target=run, daemon=True).start()

        button = ctk.CTkButton(
            parent, text=label, height=scaled(42), corner_radius=10,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(13)),
            fg_color=self.c["BG_CARD_ALT"], hover_color=self.c["BORDER"],
            command=on_click,
        )
        button.pack(fill="x", pady=(0, 6))
        status_label.pack(anchor="w", pady=(0, 12))

    def _split_columns(self, parent):
        """Arma un layout de 2 columnas (izquierda/derecha) + una fila de
        botones fija abajo, y devuelve (left_scroll, right_scroll, buttons_row).

        La izquierda (enunciado o codigo generado) lleva mas letra corrida
        que la derecha (opciones de quiz, mas cortas), asi que se le da
        mas ancho relativo (60/40) en vez de partir la pantalla al medio.
        """
        body = ctk.CTkFrame(parent, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=36, pady=(10, 20))
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)

        left = ctk.CTkScrollableFrame(body, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        right = ctk.CTkScrollableFrame(body, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        buttons_row = ctk.CTkFrame(body, fg_color="transparent")
        buttons_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(14, 0))

        return left, right, buttons_row

    def _build_quiz(
        self, parent, questions: list[QuizQuestion], answers: dict[int, ctk.IntVar],
        title: str, wraplength: int = 380, generation_error: str = "",
    ):
        answers.clear()
        self._section(parent, title)
        wraplength = wrap(wraplength)
        if not questions:
            text = "No se generaron preguntas para este caso."
            if generation_error:
                text += f" ({generation_error})"
            ctk.CTkLabel(
                parent, text=text, wraplength=wraplength, justify="left",
                font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12)), text_color=self.c["TEXT_MUTED"],
            ).pack(anchor="w", pady=(0, 12))
            return

        dot_size = scaled(20)
        indent = dot_size + scaled(8) + scaled(20)
        for i, question in enumerate(questions):
            card = ctk.CTkFrame(parent, fg_color=self.c["BG_CARD"], corner_radius=10)
            card.pack(fill="x", pady=(0, scaled(14)))
            ctk.CTkLabel(
                card, text=f"{i + 1}. {question.text}",
                font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(16), weight="bold"),
                wraplength=wraplength, justify="left", anchor="w",
            ).pack(anchor="w", fill="x", padx=scaled(16), pady=(scaled(14), scaled(10)))

            var = ctk.IntVar(value=-1)
            answers[i] = var
            for j, option in enumerate(question.options):
                # CTkRadioButton no soporta wraplength -- se usa sin texto propio,
                # emparejado con un CTkLabel aparte que sí puede envolver texto largo.
                option_row = ctk.CTkFrame(card, fg_color="transparent")
                option_row.pack(anchor="w", fill="x", padx=scaled(26), pady=scaled(6))
                ctk.CTkRadioButton(
                    option_row, text="", variable=var, value=j,
                    fg_color=self.c["ACCENT"], width=dot_size,
                    radiobutton_width=dot_size, radiobutton_height=dot_size,
                ).pack(side="left")
                option_label = ctk.CTkLabel(
                    option_row, text=option, font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(14)),
                    wraplength=wraplength - indent, justify="left", anchor="w", cursor="hand2",
                )
                option_label.pack(side="left", padx=(scaled(8), 0), fill="x", expand=True)
                option_label.bind("<Button-1>", lambda _e, v=var, idx=j: v.set(idx))
            ctk.CTkLabel(card, text="", height=scaled(8)).pack()

    def _require_all_answered(self, button, answers: dict[int, ctk.IntVar]):
        """Deja `button` deshabilitado hasta que se respondan todas las
        preguntas del cuestionario. Si no se generaron preguntas (answers
        vacio) no bloquea nada, para no dejar al participante trabado."""
        if not answers:
            return
        enabled_text = button.cget("text")

        def refresh(*_):
            if not button.winfo_exists():
                return
            pending = sum(1 for var in answers.values() if var.get() < 0)
            if pending:
                button.configure(state="disabled", text=f"Responde todas las preguntas ({pending} pendientes)")
            else:
                button.configure(state="normal", text=enabled_text)

        for var in answers.values():
            var.trace_add("write", refresh)
        refresh()

    @staticmethod
    def _answers_as_ints(answers: dict[int, ctk.IntVar]) -> dict[int, int]:
        return {i: var.get() for i, var in answers.items()}

    def _save_answers(self, stage: str, questions: list[QuizQuestion], answers: dict[int, ctk.IntVar]):
        if not questions:
            return
        participant = self.app.store.get_active()
        if participant is None:
            return
        save_quiz_answers(
            participant["number"], self.current_game.name, stage,
            questions, self._answers_as_ints(answers),
        )

    # ---------------- corte por etapa (ver stage_capture.py) ----------------
    def _export_stage(
        self, stage_number: int, questions: Optional[list[QuizQuestion]] = None,
        answers: Optional[dict[int, int]] = None,
    ):
        """Recorta por tiempo (StageTimer) los CSV continuos de
        NeuroSky/Emotion/Eye para `stage_number` y los exporta a la carpeta
        de esa etapa en el Escritorio, junto con el cuestionario (si se
        pasa). Se llama al terminar las etapas 2, 4 y 5 -- la 3 recorta
        los mismos sensores pero desde _save_stage3_files (no tiene
        cuestionario, sino prompt + registro del enunciado), y la 1/6 no
        capturan datos.

        Solo recorta los dispositivos habilitados para esta sesion (ver
        self._enabled_devices / App._ask_session_devices) -- si NeuroSky o
        la Camara no se usaron, directamente no se le pasa su DataFrame a
        write_stage_sensor_files (ver ahi por que None -- "no se uso" --
        es distinto de un CSV vacio)."""
        participant = self.app.store.get_active()
        window = self._stage_timer.finish(stage_number)
        if participant is None or self.current_game is None:
            return

        challenge_number = self.game_index + 1
        # Las etapas 3/4/5 se versionan por intento (ver "Reintentar este
        # desafío"); la 2 nunca se rehace, asi que no lleva subcarpeta.
        attempt = self._attempt_number if stage_number in (3, 4, 5) else None
        folder = stage_dir(participant, challenge_number, stage_number, attempt=attempt)

        warnings, sync_sources = self._write_stage_sensors(participant, folder, window)

        if questions:
            write_cuestionario_txt(folder, questions, answers or {})

        write_sync_timeline(folder, window, sync_sources)
        if warnings:
            self._stage_warnings[stage_number] = warnings

    def _write_stage_sensors(self, participant: dict, folder: Path, window) -> tuple[list[str], dict]:
        """Recorta NeuroSky/Emotion/Eye a la ventana `window` de una etapa
        y escribe sus CSV en `folder` (compartido por _export_stage y
        _save_stage3_files). Devuelve (advertencias, fuentes para
        sync_timeline.json)."""
        start = window.started_at
        end = window.ended_at or window.started_at

        neurosky_df = emotion_df = eye_df = None
        warnings: list[str] = []
        sync_sources: dict = {}

        if "neurosky" in self._enabled_devices:
            neurosky_df, neurosky_warnings = slice_neurosky(NEUROSKY_DATA_FILE, start, end)
            warnings += neurosky_warnings
            sync_sources["neurosky"] = source_info(neurosky_df, "Timestamp_Human", neurosky_warnings)

        if "camera" in self._enabled_devices:
            emotion_df, emotion_warnings = slice_emotion(emotion_log_file(participant), start, end)
            eye_df, eye_warnings = slice_eye(eye_log_file(participant), start, end)
            warnings += emotion_warnings + eye_warnings
            sync_sources["emotion"] = source_info(emotion_df, "timestamp", emotion_warnings)
            sync_sources["eye"] = source_info(eye_df, "timestamp", eye_warnings)

        write_stage_sensor_files(folder, neurosky_df, emotion_df, eye_df)
        return warnings, sync_sources

    def _render_pending_warnings(self, parent):
        """Banner inline (nunca un messagebox bloqueante) con las
        advertencias de la ultima exportacion de etapa -- p.ej. un sensor
        sin señal durante esa etapa. Se muestra una sola vez, en la
        pantalla siguiente a la que disparo la exportacion."""
        if not self._stage_warnings:
            return
        all_warnings = [w for warnings in self._stage_warnings.values() for w in warnings]
        self._stage_warnings.clear()
        if not all_warnings:
            return

        banner = ctk.CTkFrame(
            parent, fg_color=self.c["BG_CARD_ALT"], corner_radius=8,
            border_width=1, border_color=self.c["WARNING"],
        )
        banner.pack(fill="x", padx=36, pady=(6, 0))
        text = "\n".join(f"⚠️  {w}" for w in all_warnings)
        ctk.CTkLabel(
            banner, text=text, font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(11)),
            text_color=self.c["WARNING"], justify="left", wraplength=wrap(900),
        ).pack(anchor="w", padx=12, pady=8)

    # ---------------- flujo ----------------
    def start(self, enabled_devices: Optional[set[str]] = None):
        """`enabled_devices` es el subconjunto de ALL_DEVICES elegido por
        el evaluador en el modal previo (ver App._ask_session_devices) --
        None (todos habilitados) es solo un respaldo, por si algo llama a
        start() sin pasarlo."""
        participant = self.app.store.get_active()
        saved_index = 0
        if participant:
            saved_index = participant.get("attributes", {}).get(PROGRESS_ATTRIBUTE, 0)
        if not isinstance(saved_index, int) or not (0 <= saved_index < len(GUIDED_SESSION_GAME_ORDER)):
            saved_index = 0
        self.game_index = saved_index
        self._session_completed = False
        self._enabled_devices = set(enabled_devices) if enabled_devices is not None else set(ALL_DEVICES)
        self._show_next_setup_screen(after=None)

    def _show_next_setup_screen(self, after: Optional[str]):
        """Pantallas de configuracion previas a la Bienvenida (reloj ->
        NeuroSky -> Camara, ver ALL_DEVICES) -- salta las de cualquier
        dispositivo que el evaluador haya destildado en el modal previo
        (ver self._enabled_devices), sin dejar de lanzar/configurar nada
        de los que si estan habilitados. `after` es el dispositivo cuya
        pantalla se acaba de terminar (None al arrancar la sesion, ver
        start()) -- se llama desde el boton "Listo"/callback de cierre de
        cada una de esas pantallas en vez de encadenarlas directo entre
        si, para que agregar/quitar un dispositivo de ALL_DEVICES no
        requiera tocar cada pantalla."""
        screens = {
            "heart_rate": self._show_configure_watch,
            "neurosky": self._show_configure_neurosky,
            "camera": self._show_configure_camera_tracker,
        }
        remaining = ALL_DEVICES[ALL_DEVICES.index(after) + 1:] if after is not None else ALL_DEVICES
        for device in remaining:
            if device in self._enabled_devices:
                screens[device]()
                return
        self._show_welcome()

    def _show_configure_watch(self):
        """Pantalla previa a la bienvenida, para el evaluador: dale tiempo
        de dejar el reloj del participante midiendo antes de arrancar la
        sesion (la vé el evaluador, no el participante)."""
        self._clear()
        wrapper = ctk.CTkFrame(self.container, fg_color="transparent")
        wrapper.pack(expand=True)

        ctk.CTkLabel(
            wrapper, text="⌚", font=ctk.CTkFont(size=scaled(64)),
        ).pack(pady=(0, 10))
        ctk.CTkLabel(
            wrapper, text="Evaluador: Configurar Reloj",
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(24), weight="bold"),
        ).pack()
        ctk.CTkLabel(
            wrapper,
            text="Antes de continuar, preparen el reloj y el teléfono del participante:",
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(13)), text_color=self.c["TEXT_MUTED"],
            justify="center",
        ).pack(pady=(14, 18))

        list_frame = ctk.CTkFrame(wrapper, fg_color="transparent")
        list_frame.pack(pady=(0, 6))
        for item in (
            "Medición continua", "Elegir entreno: otros tipos", "Desactivar notificaciones del reloj",
            "Conectar teléfono",
        ):
            ctk.CTkLabel(
                list_frame, text=f"•  {item}",
                font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(14)),
            ).pack(anchor="w", pady=(0, 6))

        ctk.CTkLabel(
            wrapper,
            text="(el teléfono ya conectado a la compu -- USB, KDE Connect, etc. -- agiliza\n"
                 "pasar después la carpeta de datos del reloj, ver \"Importar reloj\")",
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(11)), text_color=self.c["TEXT_MUTED"],
            justify="center",
        ).pack(pady=(0, 18))

        ctk.CTkButton(
            wrapper, text="Listo  ▶", width=scaled(200), height=scaled(42), corner_radius=10,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(14), weight="bold"),
            fg_color=self.c["ACCENT"], hover_color=self.c["ACCENT_HOVER"],
            command=lambda: self._show_next_setup_screen(after="heart_rate"),
        ).pack()
        self._exit_button(self.container)

    # ---------------- Configuracion Neurosky ----------------
    def _show_configure_neurosky(self):
        """Pantalla previa a la bienvenida, para el evaluador: abre la
        ventana aparte "Datos del Neurosky" (ver _open_neurosky_window) y
        ahi mismo dispara la vinculacion bluetooth + lanzamiento de
        tools/NeuroSky/test_neurosky.py. Esa ventana -- con su propio
        estado y boton de reconexion -- se queda abierta durante TODA la
        sesion, no solo en esta pantalla: si el dispositivo se desconecta
        a mitad de un desafio, se puede reconectar desde ahi sin volver
        a esta pantalla ni reiniciar la sesion guiada.
        """
        self._clear()
        self._open_neurosky_window()
        self._start_neurosky_setup_thread()

        wrapper = ctk.CTkFrame(self.container, fg_color="transparent")
        wrapper.pack(expand=True)

        ctk.CTkLabel(
            wrapper, text="🧠", font=ctk.CTkFont(size=scaled(64)),
        ).pack(pady=(0, 10))
        ctk.CTkLabel(
            wrapper, text="Evaluador: Neurosky",
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(24), weight="bold"),
        ).pack()
        ctk.CTkLabel(
            wrapper,
            text="Vinculando el dispositivo y verificando la señal -- mira\n"
                 "el estado y las lecturas en la ventana \"Datos del Neurosky\".",
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(13)), text_color=self.c["TEXT_MUTED"],
            justify="center",
        ).pack(pady=(14, 24))
        ctk.CTkButton(
            wrapper, text="Listo  ▶", width=scaled(200), height=scaled(42), corner_radius=10,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(14), weight="bold"),
            fg_color=self.c["ACCENT"], hover_color=self.c["ACCENT_HOVER"],
            command=self._finish_neurosky_setup,
        ).pack()
        self._exit_button(self.container)

    def _start_neurosky_setup_thread(self):
        if self._neurosky_setup_running:
            return
        self._neurosky_setup_running = True
        threading.Thread(target=self._run_neurosky_setup_guarded, daemon=True).start()

    def _run_neurosky_setup_guarded(self):
        try:
            self._run_neurosky_setup()
        finally:
            self._neurosky_setup_running = False

    def _run_neurosky_setup(self):
        """Vincula el Neurosky y arranca test_neurosky.py -- corre en un
        hilo de fondo, tanto al llegar a _show_configure_neurosky como
        cada vez que se toca "🔄 Reconectar" en la ventana "Datos del
        Neurosky" (a mitad de sesion, si el dispositivo se desconecto)."""
        self._stop_neurosky_process()
        self._show_neurosky_reconnect(False)

        password = None
        if sudo_needs_password():
            self._set_neurosky_status("Esperando la contraseña de administrador...")
            password = self._ask_sudo_password_blocking()
            if password is None:
                self._log_neurosky(
                    "[CANCELADO] No se ingresó la contraseña -- no se pudo vincular el dispositivo.",
                )
                self._set_neurosky_status(
                    "No se pudo vincular el dispositivo (contraseña cancelada).", color=self.c["WARNING"],
                )
                self._show_neurosky_reconnect(True)
                return

        self._set_neurosky_status("Vinculando el dispositivo por bluetooth...")
        if not bind_neurosky(self._log_neurosky, password=password):
            self._set_neurosky_status(
                "No se pudo vincular el dispositivo. Revisá el detalle arriba.", color=self.c["WARNING"],
            )
            self._show_neurosky_reconnect(True)
            return

        self._log_neurosky(f"[OK] Vinculación bluetooth lista en {RFCOMM_DEVICE}.")
        self._set_neurosky_status("Vinculación lista. Iniciando lectura de señales...")

        try:
            process = start_neurosky_test()
        except FileNotFoundError as exc:
            self._log_neurosky(f"[ERROR] {exc}")
            self._set_neurosky_status("No se pudo iniciar test_neurosky.py.", color=self.c["WARNING"])
            self._show_neurosky_reconnect(True)
            return

        self._neurosky_process = process
        self._neurosky_last_data_at = time.monotonic()
        for raw_line in process.stdout:
            self._handle_neurosky_line(raw_line.rstrip())

        returncode = process.wait()
        if self._neurosky_process is process:
            self._neurosky_process = None

        # returncode != 0 acá significa que test_neurosky.py salio solo
        # (se desconecto el bluetooth, se quedo sin bateria, etc.) -- NO
        # por el SIGINT de "Salir"/reconectar, que ya limpia
        # self._neurosky_process ANTES de mandar la señal (ver
        # _stop_neurosky_process), asi que esta rama nunca compite con eso.
        if returncode != 0:
            self._log_neurosky(f"[ERROR] test_neurosky.py terminó con código {returncode}.")
            self._set_neurosky_status(
                "Se perdió la conexión con el dispositivo. Enciéndelo/acércalo y toca Reconectar.",
                color=self.c["WARNING"],
            )
            self._show_neurosky_reconnect(True)

    def _handle_neurosky_line(self, line: str):
        self._log_neurosky(line)
        self._neurosky_last_data_at = time.monotonic()
        lower = line.lower()
        if "[error]" in lower:
            self._set_neurosky_status(
                "⚠️  Error -- revisa que el dispositivo esté encendido y con batería.",
                color=self.c["WARNING"],
            )
        elif "[contacto ok]" in lower:
            self._set_neurosky_status("🟢  Señal OK -- recibiendo datos del NeuroSky.")
        elif "[ajustando" in lower:
            self._set_neurosky_status("🟡  Contacto detectado, ajustando la señal...")
        elif "[sin contacto" in lower:
            self._set_neurosky_status("🔴  Sin contacto -- revisa la posición del sensor.")

    def _neurosky_watchdog_tick(self):
        """Se reagenda solo cada 5s (ver _open_neurosky_window) mientras la
        ventana "Datos del Neurosky" siga abierta -- si el proceso sigue
        vivo pero hace rato que no manda ninguna linea (el dispositivo se
        colgo o perdio señal sin que el proceso llegara a caerse), lo
        marca en el estado y ofrece reconectar en vez de quedarse mudo sin
        ninguna explicacion."""
        if self._neurosky_window is None:
            return  # ventana cerrada (o sesion terminada) -- no hace falta seguir chequeando

        process = self._neurosky_process
        if process is not None and process.poll() is None and self._neurosky_last_data_at is not None:
            elapsed = time.monotonic() - self._neurosky_last_data_at
            if elapsed > NEUROSKY_STALE_SECONDS:
                self._set_neurosky_status(
                    f"⚠️  Sin señal hace {int(elapsed)}s -- revisa el dispositivo o toca Reconectar.",
                    color=self.c["WARNING"],
                )
                self._show_neurosky_reconnect(True)

        self.app.after(5000, self._neurosky_watchdog_tick)

    def _ask_sudo_password_blocking(self) -> Optional[str]:
        """Se llama desde el hilo de fondo de `_show_configure_neurosky`:
        agenda el modal de contraseña en el hilo de Tk (los widgets de Tk
        solo se pueden crear/tocar ahi) y bloquea ese hilo de fondo hasta
        que el usuario confirme o cancele."""
        result: dict[str, Optional[str]] = {}
        done = threading.Event()

        def show_modal():
            modal = ctk.CTkToplevel(self.app)
            modal.title("Contraseña de administrador")
            modal.geometry(f"{wrap(380)}x{wrap(230)}")
            modal.configure(fg_color=self.c["BG_CARD"])
            modal.transient(self.app)
            modal.resizable(False, False)
            modal.wait_visibility()
            # La ventana "Datos del Neurosky" es topmost (ver
            # _open_neurosky_window) -- si este modal no lo fuera tambien,
            # podria terminar tapado detras suyo mientras igual le retiene
            # el foco de teclado (grab_set), dando la sensacion de que la
            # app se congelo.
            modal.attributes("-topmost", True)
            modal.lift()
            modal.focus_force()
            modal.grab_set()

            def finish(value: Optional[str]):
                result["value"] = value
                modal.destroy()
                done.set()

            modal.protocol("WM_DELETE_WINDOW", lambda: finish(None))

            ctk.CTkLabel(
                modal, text="🔒  Vincular el Neurosky requiere sudo",
                font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(14), weight="bold"),
            ).pack(pady=(24, 6))
            ctk.CTkLabel(
                modal,
                text="Ingresá tu contraseña de administrador para\n"
                     "vincular el dispositivo por bluetooth (rfcomm bind).",
                font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(11)), text_color=self.c["TEXT_MUTED"],
                justify="center",
            ).pack(pady=(0, 12))

            entry = ctk.CTkEntry(
                modal, width=scaled(240), height=scaled(34), corner_radius=8,
                show="•", placeholder_text="Contraseña",
            )
            entry.pack()
            entry.focus_set()
            entry.bind("<Return>", lambda _e: finish(entry.get()))

            buttons_row = ctk.CTkFrame(modal, fg_color="transparent")
            buttons_row.pack(pady=(18, 0))
            ctk.CTkButton(
                buttons_row, text="Cancelar", width=scaled(100), height=scaled(32), corner_radius=8,
                font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12)),
                fg_color="transparent", hover_color=self.c["BORDER"], border_width=1,
                border_color=self.c["BORDER"],
                command=lambda: finish(None),
            ).pack(side="left", padx=(0, 8))
            ctk.CTkButton(
                buttons_row, text="Aceptar", width=scaled(100), height=scaled(32), corner_radius=8,
                font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12), weight="bold"),
                fg_color=self.c["ACCENT"], hover_color=self.c["ACCENT_HOVER"],
                command=lambda: finish(entry.get()),
            ).pack(side="left")

        self.app.after(0, show_modal)
        done.wait()
        return result.get("value") or None

    def _open_neurosky_window(self):
        """Ventana APARTE (no un frame dentro de la sesion guiada) con el
        estado, las lecturas en vivo y su propio boton de reconexion -- se
        abre una sola vez, al llegar a la pantalla de configuracion, y
        queda arriba durante el resto de la sesion (no es hija de
        self.container, asi que _clear() no la toca al cambiar de etapa)
        para poder seguir viendo los datos -- y reconectar si hace falta --
        mientras el participante resuelve los desafios.
        """
        self._close_neurosky_window()

        window = ctk.CTkToplevel(self.app)
        window.title("Datos del Neurosky")
        win_w, win_h = wrap(640), wrap(460)
        # Arriba a la derecha, no centrada -- si quedara centrada sobre la
        # ventana principal (que arranca maximizada), CUALQUIER click ahi
        # (p.ej. "Listo") reenfoca/levanta la principal y la tapa entera,
        # dando la impresion de que dejo de recibir datos.
        margin = scaled(24)
        pos_x = max(self.app.winfo_screenwidth() - win_w - margin, 0)
        pos_y = margin
        window.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")
        window.configure(fg_color=self.c["BG_CARD"])
        # "Siempre visible": es una ventana de monitoreo que tiene que
        # seguir a la vista durante TODA la sesion, sin importar que
        # pantalla del wizard este enfocada -- sin esto, la ventana
        # principal la tapa apenas se interactua con ella.
        window.attributes("-topmost", True)

        ctk.CTkLabel(
            window, text="🧠  Datos del Neurosky en vivo",
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(15), weight="bold"),
        ).pack(anchor="w", padx=16, pady=(16, 4))

        # header_frame se empaqueta UNA sola vez, fijo arriba de la
        # terminal -- status_label y retry_button viven adentro para que
        # mostrar/ocultar el boton (pack/pack_forget, ver
        # _show_neurosky_reconnect) reordene solo DENTRO de este frame y
        # nunca termine debajo de la terminal (que ya esta empaquetada con
        # fill="both", expand=True).
        header_frame = ctk.CTkFrame(window, fg_color="transparent")
        header_frame.pack(anchor="w", fill="x", padx=16, pady=(0, 4))

        status_label = ctk.CTkLabel(
            header_frame, text="Iniciando...", font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12)),
            text_color=self.c["TEXT_MUTED"], anchor="w", justify="left",
        )
        status_label.pack(anchor="w", fill="x", pady=(0, 6))

        retry_button = ctk.CTkButton(
            header_frame, text="🔄  Reconectar", width=scaled(160), height=scaled(34), corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12)),
            fg_color=self.c["BG_CARD_ALT"], hover_color=self.c["BORDER"],
            command=self._start_neurosky_setup_thread,
        )
        # No se empaqueta todavia: solo aparece si hace falta reconectar
        # (ver _show_neurosky_reconnect), asi la ventana no queda con un
        # boton de "arreglar algo" cuando todo esta funcionando bien.

        terminal = ctk.CTkTextbox(
            window, fg_color=self.c["BG_CARD_ALT"], wrap="word",
            font=ctk.CTkFont(family="monospace", size=scaled(12)),
        )
        terminal.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        terminal.configure(state="disabled")

        def on_window_close():
            self._neurosky_window = None
            self._neurosky_terminal = None
            self._neurosky_status_label = None
            self._neurosky_retry_button = None
            window.destroy()

        window.protocol("WM_DELETE_WINDOW", on_window_close)

        self._neurosky_window = window
        self._neurosky_terminal = terminal
        self._neurosky_status_label = status_label
        self._neurosky_retry_button = retry_button
        self._neurosky_last_data_at = None

        self.app.after(5000, self._neurosky_watchdog_tick)

    def _close_neurosky_window(self):
        # window se agarra y las referencias se limpian YA (atomico por el
        # GIL, no hace falta el hilo de Tk para esto) -- solo
        # window.destroy() se difiere. Si esto se llama de nuevo (p.ej.
        # _open_neurosky_window abriendo una ventana nueva) antes de que
        # el destroy() diferido corra, tiene que destruir la ventana VIEJA
        # que ya capturo aca, no la que self._neurosky_window tenga para
        # entonces.
        window = self._neurosky_window
        self._neurosky_window = None
        self._neurosky_terminal = None
        self._neurosky_status_label = None
        self._neurosky_retry_button = None
        if window is None:
            return

        def do():
            try:
                window.destroy()
            except Exception:
                pass
        self.app.after(0, do)

    def _log_neurosky(self, line: str):
        """Le puede llegar una linea desde el hilo de fondo mucho despues
        de que el evaluador siguio de largo (la ventana "Datos del
        Neurosky" puede seguir abierta, o el usuario la pudo haber
        cerrado a mano) -- si el widget ya no existe, no hace nada."""
        def do():
            terminal = self._neurosky_terminal
            if terminal is None:
                return
            try:
                terminal.configure(state="normal")
                terminal.insert("end", line + "\n")
                terminal.see("end")
                terminal.configure(state="disabled")
            except Exception:
                self._neurosky_terminal = None
        self.app.after(0, do)

    def _set_neurosky_status(self, text: str, color: Optional[str] = None):
        def do():
            label = self._neurosky_status_label
            if label is None:
                return
            try:
                label.configure(text=text, text_color=color or self.c["TEXT_MUTED"])
            except Exception:
                self._neurosky_status_label = None
        self.app.after(0, do)

    def _show_neurosky_reconnect(self, show: bool):
        def do():
            button = self._neurosky_retry_button
            if button is None:
                return
            try:
                if show:
                    button.pack(anchor="w", pady=(0, 6))
                else:
                    button.pack_forget()
            except Exception:
                self._neurosky_retry_button = None
        self.app.after(0, do)

    def _stop_neurosky_process(self):
        process = self._neurosky_process
        self._neurosky_process = None
        if process is None or process.poll() is not None:
            return
        # SIGINT en vez de terminate(): test_neurosky.py solo cierra el CSV
        # ordenadamente (neuropy.stop() + file_handle.close()) al recibir un
        # KeyboardInterrupt, igual que si se presionara Ctrl+C a mano.
        try:
            process.send_signal(signal.SIGINT)
            process.wait(timeout=3)
        except Exception:
            process.terminate()

    def _finish_neurosky_setup(self):
        # A proposito NO se detiene el proceso aca -- el dispositivo se deja
        # transmitiendo en segundo plano durante toda la sesion guiada; solo
        # se corta en _exit_guided_session, cuando la sesion termina de
        # verdad (por cualquier pantalla).
        self._show_next_setup_screen(after="neurosky")

    # ---------------- Configuracion Camera Tracker (Emotion + Eye) ----------------
    def _show_configure_camera_tracker(self):
        """Pantalla previa a la bienvenida, para el evaluador: abre la
        ventana aparte "Datos de la Cámara" (ver _open_camera_window), con
        el estado, el log en vivo y el boton "Calibrar" del Camera
        Tracker -- el proceso UNICO que hace tanto Emotion Tracker como
        Eye Tracker sobre la misma camara (ver tools/camera_tracker.py:
        esta webcam, como la mayoria, no admite dos procesos con la
        camara abierta a la vez, asi que lanzarlos por separado dejaba al
        segundo sin poder abrirla). Esa ventana se queda abierta durante
        TODA la sesion, igual que la del Neurosky: si la camara se
        desconecta a mitad de un desafio, se puede recalibrar sin volver
        a esta pantalla.
        """
        self._clear()
        self._camera_calibration = None
        self._open_camera_window()

        wrapper = ctk.CTkFrame(self.container, fg_color="transparent")
        wrapper.pack(expand=True)

        ctk.CTkLabel(
            wrapper, text="📷", font=ctk.CTkFont(size=scaled(64)),
        ).pack(pady=(0, 10))
        ctk.CTkLabel(
            wrapper, text="Evaluador: Cámara (Emotion + Eye Tracker)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(24), weight="bold"),
        ).pack()
        ctk.CTkLabel(
            wrapper,
            text="Acomodá la pantalla de la computadora frente al\n"
                 "participante antes de calibrar, para mejor precisión.\n\n"
                 "Tocá \"Calibrar\" en la ventana \"Datos de la Cámara\" y\n"
                 "pedile al participante que mire hacia donde indique la\n"
                 "cámara -- primero a la IZQUIERDA, después a la DERECHA.\n"
                 "Con eso arrancan juntos el seguimiento de mirada y el\n"
                 "análisis de emociones, sobre la misma cámara.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(13)), text_color=self.c["TEXT_MUTED"],
            justify="center",
        ).pack(pady=(14, 24))

        continue_button = ctk.CTkButton(
            wrapper, text="Listo  ▶", width=scaled(200), height=scaled(42), corner_radius=10,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(14), weight="bold"),
            fg_color=self.c["ACCENT"], hover_color=self.c["ACCENT_HOVER"],
            state="disabled",
            command=self._finish_camera_tracker_setup,
        )
        continue_button.pack()
        self._camera_continue_button = continue_button

        self._exit_button(self.container)

    def _open_camera_window(self):
        """Ventana APARTE con el estado, el log en vivo y el boton
        "Calibrar" del Camera Tracker -- se abre una sola vez, al llegar
        a esta pantalla, y queda arriba durante el resto de la sesion (no
        es hija de self.container, asi que _clear() no la toca al
        cambiar de etapa), en la esquina inferior derecha -- la del
        Neurosky ya ocupa la superior derecha.
        """
        self._close_camera_window()

        window = ctk.CTkToplevel(self.app)
        window.title("Datos de la Cámara")
        win_w, win_h = wrap(520), wrap(360)
        margin = scaled(24)
        pos_x = max(self.app.winfo_screenwidth() - win_w - margin, 0)
        pos_y = max(self.app.winfo_screenheight() - win_h - margin, 0)
        window.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")
        window.configure(fg_color=self.c["BG_CARD"])
        # "Siempre visible" por el mismo motivo que la ventana del
        # Neurosky: la sesion guiada corre en pantalla completa.
        window.attributes("-topmost", True)

        ctk.CTkLabel(
            window, text="📷  Datos de la Cámara en vivo (Emotion + Eye)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(15), weight="bold"),
        ).pack(anchor="w", padx=16, pady=(16, 4))

        header_frame = ctk.CTkFrame(window, fg_color="transparent")
        header_frame.pack(anchor="w", fill="x", padx=16, pady=(0, 4))

        status_label = ctk.CTkLabel(
            header_frame, text="Sin calibrar todavía.", font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12)),
            text_color=self.c["TEXT_MUTED"], anchor="w", justify="left",
        )
        status_label.pack(anchor="w", fill="x", pady=(0, 6))

        calibrate_button = ctk.CTkButton(
            header_frame, text="🎯  Calibrar", width=scaled(160), height=scaled(34), corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12)),
            fg_color=self.c["BG_CARD_ALT"], hover_color=self.c["BORDER"],
            command=self._start_camera_calibration_thread,
        )
        calibrate_button.pack(anchor="w", pady=(0, 6))

        terminal = ctk.CTkTextbox(
            window, fg_color=self.c["BG_CARD_ALT"], wrap="word",
            font=ctk.CTkFont(family="monospace", size=scaled(12)),
        )
        terminal.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        terminal.configure(state="disabled")

        def on_window_close():
            self._camera_window = None
            self._camera_terminal = None
            self._camera_status_label = None
            self._camera_calibrate_button = None
            window.destroy()

        window.protocol("WM_DELETE_WINDOW", on_window_close)

        self._camera_window = window
        self._camera_terminal = terminal
        self._camera_status_label = status_label
        self._camera_calibrate_button = calibrate_button

    def _close_camera_window(self):
        window = self._camera_window
        self._camera_window = None
        self._camera_terminal = None
        self._camera_status_label = None
        self._camera_calibrate_button = None
        if window is None:
            return

        def do():
            try:
                window.destroy()
            except Exception:
                pass
        self.app.after(0, do)

    def _start_camera_calibration_thread(self):
        if self._camera_setup_running:
            return
        self._camera_setup_running = True
        threading.Thread(target=self._run_camera_calibration_guarded, daemon=True).start()

    def _run_camera_calibration_guarded(self):
        try:
            self._run_camera_calibration()
        finally:
            self._camera_setup_running = False

    def _run_camera_calibration(self):
        # Si ya habia un seguimiento continuo corriendo (una
        # recalibracion), se para primero -- se relanza mas abajo con los
        # umbrales nuevos.
        self._stop_camera_process()
        self._set_camera_calibrate_enabled(False)
        self._set_camera_continue_enabled(False)
        self._clear_camera_terminal()
        self._set_camera_status("🎯  Calibrando -- mira la ventana de la cámara que se abrió aparte...")

        try:
            left_x, right_x = run_calibration(self._log_camera, mirror=True)
        except Exception as exc:
            self._set_camera_status(f"⚠️  No se pudo calibrar: {exc}", color=self.c["WARNING"])
            self._set_camera_calibrate_enabled(True)
            return

        self._camera_calibration = (left_x, right_x)
        self._set_camera_status(
            f"Calibración lista (izquierda={left_x:.2f}, derecha={right_x:.2f}). "
            "Iniciando el seguimiento...",
        )

        participant = self.app.store.get_active()
        try:
            process = start_camera_tracker(participant, "sesion_guiada", left_x, right_x)
        except Exception as exc:
            self._set_camera_status(
                f"⚠️  Calibrado, pero no se pudo iniciar el seguimiento: {exc}", color=self.c["WARNING"],
            )
            self._set_camera_calibrate_enabled(True)
            return

        self._camera_process = process
        threading.Thread(target=self._pump_camera_output, args=(process,), daemon=True).start()

        self._set_camera_status(
            f"🟢  Corriendo (izquierda={left_x:.2f}, derecha={right_x:.2f}) -- Emotion + Eye Tracker.",
        )
        self._set_camera_calibrate_enabled(True)  # por si quiere recalibrar
        self._set_camera_continue_enabled(True)

    def _pump_camera_output(self, process: subprocess.Popen):
        for line in process.stdout:
            self._log_camera(line.rstrip())
        process.wait()
        if self._camera_process is process:
            self._camera_process = None
            self._set_camera_status(
                "⚠️  El Camera Tracker se cerró -- vuelve a calibrar antes de continuar.",
                color=self.c["WARNING"],
            )
            self._set_camera_continue_enabled(False)

    def _log_camera(self, line: str):
        def do():
            terminal = self._camera_terminal
            if terminal is None:
                return
            try:
                terminal.configure(state="normal")
                terminal.insert("end", line + "\n")
                terminal.see("end")
                terminal.configure(state="disabled")
            except Exception:
                self._camera_terminal = None
        self.app.after(0, do)

    def _clear_camera_terminal(self):
        def do():
            terminal = self._camera_terminal
            if terminal is None:
                return
            try:
                terminal.configure(state="normal")
                terminal.delete("1.0", "end")
                terminal.configure(state="disabled")
            except Exception:
                self._camera_terminal = None
        self.app.after(0, do)

    def _set_camera_status(self, text: str, color: Optional[str] = None):
        def do():
            label = self._camera_status_label
            if label is None:
                return
            try:
                label.configure(text=text, text_color=color or self.c["TEXT_MUTED"])
            except Exception:
                self._camera_status_label = None
        self.app.after(0, do)

    def _set_camera_calibrate_enabled(self, enabled: bool):
        def do():
            button = self._camera_calibrate_button
            if button is None:
                return
            try:
                button.configure(state="normal" if enabled else "disabled")
            except Exception:
                self._camera_calibrate_button = None
        self.app.after(0, do)

    def _set_camera_continue_enabled(self, enabled: bool):
        def do():
            button = self._camera_continue_button
            if button is None:
                return
            try:
                button.configure(state="normal" if enabled else "disabled")
            except Exception:
                self._camera_continue_button = None
        self.app.after(0, do)

    def _stop_camera_process(self):
        process = self._camera_process
        self._camera_process = None
        if process is None or process.poll() is not None:
            return
        try:
            process.send_signal(signal.SIGINT)
            process.wait(timeout=3)
        except Exception:
            process.terminate()

    def _finish_camera_tracker_setup(self):
        # A proposito NO se detiene el proceso aca -- el seguimiento se deja
        # corriendo en segundo plano durante toda la sesion guiada; solo se
        # corta en _exit_guided_session.
        self._show_next_setup_screen(after="camera")

    def _save_progress(self, next_game_index: int):
        participant = self.app.store.get_active()
        if participant is None:
            return
        self.app.store.set_attribute(participant["id"], PROGRESS_ATTRIBUTE, next_game_index)

    def _clear_progress(self):
        participant = self.app.store.get_active()
        if participant is None:
            return
        self.app.store.clear_attribute(participant["id"], PROGRESS_ATTRIBUTE)

    def _show_welcome(self):
        self._clear()
        participant = self.app.store.get_active()
        wrapper = ctk.CTkFrame(self.container, fg_color="transparent")
        wrapper.pack(expand=True)

        ctk.CTkLabel(
            wrapper, text="👋", font=ctk.CTkFont(size=scaled(48)),
        ).pack(pady=(0, 10))
        record = load_personal_record(participant["number"])
        display_name = f"{record[0]} {record[1]}".strip() if record else participant_label(participant)
        ctk.CTkLabel(
            wrapper, text=f"Bienvenido/a, {display_name}",
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(24), weight="bold"),
        ).pack()
        if self.game_index > 0:
            intro_text = (
                f"Retomás donde dejaste, en el desafío {self.game_index + 1} de "
                f"{len(GUIDED_SESSION_GAME_ORDER)}.\n\n"
                "Vas a resolver una serie de desafíos de programación escribiendo\n"
                "tu propio prompt para pedirle a una IA que lo resuelva. Cada\n"
                "desafío tiene 6 etapas:\n\n"
                "Etapa 1: Jugar el juego sin la solución del desafío.\n"
                "Etapa 2: Leer el enunciado y responder 7 preguntas sobre él.\n"
                "Etapa 3: Escribir tu prompt para resolverlo.\n"
                "Etapa 4: Ver el resultado y responder 7 preguntas sobre la solución.\n"
                "Etapa 5: Responder 7 preguntas de razonamiento sobre esa solución.\n"
                "Etapa 6: Ver esa misma solución en acción, dentro del juego."
            )
        else:
            intro_text = (
                "Vas a resolver una serie de desafíos de programación, del más\n"
                "fácil al más difícil, escribiendo tu propio prompt para pedirle\n"
                "a una IA que lo resuelva. Cada desafío tiene 6 etapas:\n\n"
                "Etapa 1: Jugar el juego sin la solución del desafío.\n"
                "Etapa 2: Leer el enunciado y responder 7 preguntas sobre él.\n"
                "Etapa 3: Escribir tu prompt para resolverlo.\n"
                "Etapa 4: Ver el resultado y responder 7 preguntas sobre la solución.\n"
                "Etapa 5: Responder 7 preguntas de razonamiento sobre esa solución.\n"
                "Etapa 6: Ver esa misma solución en acción, dentro del juego.\n\n"
                "Vamos a empezar con el desafío más fácil."
            )
        ctk.CTkLabel(
            wrapper,
            text=intro_text,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(13)), text_color=self.c["TEXT_MUTED"],
            justify="center",
        ).pack(pady=(14, 24))
        ctk.CTkButton(
            wrapper, text="Comenzar  ▶", width=scaled(200), height=scaled(42), corner_radius=10,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(14), weight="bold"),
            fg_color=self.c["ACCENT"], hover_color=self.c["ACCENT_HOVER"],
            command=self._start_current_game,
        ).pack()
        self._exit_button(self.container)

    def _start_current_game(self):
        game_name = GUIDED_SESSION_GAME_ORDER[self.game_index]
        games_by_name = {g.name: g for g in discover_games()}
        self.current_game = games_by_name.get(game_name)
        self.current_challenge = get_challenge(game_name)
        self.current_result = None
        self._attempt_number = 1
        self._stage_warnings.clear()
        if self.current_game is None or self.current_challenge is None:
            self._advance_or_finish()
            return
        self._show_stage1()

    # ---------------- Etapa 1 ----------------
    def _show_stage1(self):
        self._clear()
        challenge = self.current_challenge
        game = self.current_game

        self._header(self.container, "ETAPA 1 DE 6 · VER EL JUEGO", game.display_name)
        self._exit_button(self.container)

        body = ctk.CTkFrame(self.container, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=36, pady=(10, 20))

        ctk.CTkLabel(
            body,
            text=(
                "Antes de leer el problema, juega este juego tal como está ahora, "
                "SIN el algoritmo del desafío resuelto -- probablemente notes un "
                "comportamiento roto o incompleto justo en esa parte. Todavía no "
                "hace falta que entiendas POR QUÉ pasa eso: esto es solo un "
                "vistazo previo, el entendimiento real viene con el enunciado "
                "que sigue. El juego se abre en pantalla completa -- presiona "
                "ESC para salir de él cuando termines de probarlo, y continúa."
            ),
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(13)), text_color=self.c["TEXT_MUTED"],
            wraplength=wrap(900), justify="left",
        ).pack(anchor="w", pady=(0, 14))

        symptom_card = ctk.CTkFrame(body, fg_color=self.c["BG_CARD_ALT"], corner_radius=10)
        symptom_card.pack(anchor="w", fill="x", pady=(0, 16))
        ctk.CTkLabel(
            symptom_card, text="🔍  Qué probar en esta etapa",
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(13), weight="bold"),
            text_color=self.c["ACCENT"],
        ).pack(anchor="w", padx=16, pady=(12, 4))
        ctk.CTkLabel(
            symptom_card, text=challenge.broken_symptom,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(13)),
            wraplength=wrap(860), justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 14))

        self._play_button(
            body, "🎮  Jugar sin la solución",
            lambda: launch_game_without_solution(game),
        )

        ctk.CTkButton(
            body, text="Ya lo probé · Leer el problema  ▶", height=scaled(42), corner_radius=10,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(13), weight="bold"),
            fg_color=self.c["ACCENT"], hover_color=self.c["ACCENT_HOVER"],
            command=self._show_stage2,
        ).pack(fill="x", pady=(16, 0))

    # ---------------- Etapa 2 ----------------
    def _show_stage2(self):
        self._clear()
        challenge = self.current_challenge
        game = self.current_game
        self._stage_timer.start(2)

        self._header(self.container, "ETAPA 2 DE 6 · EL PROBLEMA", challenge.title)
        self._exit_button(self.container)

        left, right, buttons_row = self._split_columns(self.container)

        render_statement(left, game, challenge, self.c, wraplength=420, font_scale=2.0)

        self._build_quiz(
            right, get_statement_questions(game.name), self.stage1_answers,
            title="📝  Preguntas sobre el enunciado",
        )

        def on_continue():
            questions = get_statement_questions(game.name)
            self._save_answers("etapa1_enunciado", questions, self.stage1_answers)
            self._export_stage(2, questions, self._answers_as_ints(self.stage1_answers))
            self._show_stage3()

        continue_button = ctk.CTkButton(
            buttons_row, text="Ya entendí el problema · Escribir mi prompt  ▶", height=scaled(42), corner_radius=10,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(13), weight="bold"),
            fg_color=self.c["ACCENT"], hover_color=self.c["ACCENT_HOVER"],
            command=on_continue,
        )
        continue_button.pack(fill="x")
        self._require_all_answered(continue_button, self.stage1_answers)

    # ---------------- Ventana del enunciado (Etapa 3) ----------------
    def _toggle_statement_window(self, game, challenge):
        """Abre (o, si ya esta abierta, simplemente trae al frente) una
        ventana aparte con el enunciado completo del desafio -- para que
        el participante pueda consultarlo mientras escribe su prompt sin
        perder de vista lo que ya escribio. No es modal (no bloquea la
        ventana principal) y se puede mover/redimensionar libremente.
        """
        if self._statement_window is not None:
            try:
                self._statement_window.deiconify()
                self._statement_window.lift()
                self._statement_window.focus_force()
                return
            except Exception:
                self._statement_window = None

        self._statement_log.append({"opened_at": datetime.now(), "closed_at": None})

        window = ctk.CTkToplevel(self.app)
        window.title(f"Enunciado -- {challenge.title}")
        win_w, win_h = wrap(560), wrap(680)
        # A un costado, no centrada -- para poder consultarla al lado del
        # cuadro de texto en vez de taparlo.
        margin = scaled(24)
        pos_x = max(self.app.winfo_screenwidth() - win_w - margin, 0)
        pos_y = margin
        window.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")
        window.configure(fg_color=self.c["BG_CARD"])
        # La sesion guiada corre en pantalla completa (ver
        # App.enter_session_wizard) -- sin esto, esta ventana quedaria
        # tapada detras (mismo motivo que la ventana del Neurosky).
        window.attributes("-topmost", True)

        scroll = ctk.CTkScrollableFrame(window, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=18, pady=18)
        render_statement(scroll, game, challenge, self.c, wraplength=440, font_scale=1.7875)  # 1.375 + 30%

        def on_close():
            self._statement_window = None
            self._log_statement_closed()
            window.destroy()

        window.protocol("WM_DELETE_WINDOW", on_close)
        self._statement_window = window

    def _log_statement_closed(self):
        for entry in reversed(self._statement_log):
            if entry["closed_at"] is None:
                entry["closed_at"] = datetime.now()
                return

    def _close_statement_window(self):
        window = self._statement_window
        self._statement_window = None
        if window is None:
            return
        self._log_statement_closed()
        try:
            window.destroy()
        except Exception:
            pass

    # ---------------- Etapa 3 ----------------
    def _show_stage3(self):
        self._clear()
        challenge = self.current_challenge
        game = self.current_game
        self._stage_timer.start(3)
        self._statement_log = []

        self._header(self.container, "ETAPA 3 DE 6 · TU PROMPT", "Escribe el prompt para resolverlo")
        self._exit_button(self.container)
        self._render_pending_warnings(self.container)

        body = ctk.CTkFrame(self.container, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=36, pady=(10, 20))

        ctk.CTkLabel(
            body,
            text=(
                "Escribe, en tus propias palabras, el prompt que le darías a una IA "
                "para que resuelva este ejercicio. Abajo tienes, como referencia, la "
                "función exacta que hay que implementar (no hace falta que la "
                "memorices, ni es lo que se evalúa). Importante: la IA que va a "
                "responder NO va a ver el enunciado ni nada de lo que leíste antes -- "
                "solo el texto exacto que escribas acá. Si tu prompt no incluye el "
                "contexto necesario, la respuesta lo va a reflejar."
            ),
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12)), text_color=self.c["TEXT_MUTED"],
            wraplength=wrap(900), justify="left",
        ).pack(anchor="w", pady=(0, 10))

        ctk.CTkButton(
            body, text="📄  Ver enunciado del desafío", width=scaled(260), height=scaled(36), corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12)),
            fg_color=self.c["BG_CARD_ALT"], hover_color=self.c["BORDER"],
            command=lambda: self._toggle_statement_window(game, challenge),
        ).pack(anchor="w", pady=(0, 14))

        self._code_block(body, challenge.signature)

        prompt_box = ctk.CTkTextbox(
            body, wrap="word", font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(18)),
            fg_color=self.c["BG_CARD"], corner_radius=10,
        )
        prompt_box.pack(fill="both", expand=True)

        status_label = ctk.CTkLabel(
            body, text="", font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12)), text_color=self.c["TEXT_MUTED"],
        )
        status_label.pack(anchor="w", pady=(10, 0))

        send_button = ctk.CTkButton(
            body, text="Generar respuesta  ▶", height=scaled(42), corner_radius=10,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(13), weight="bold"),
            fg_color=self.c["ACCENT"], hover_color=self.c["ACCENT_HOVER"],
        )
        send_button.pack(fill="x", pady=(8, 0))

        def on_send():
            text = prompt_box.get("1.0", "end").strip()
            if not text:
                status_label.configure(text="⚠️  Escribe un prompt antes de enviarlo.", text_color=self.c["WARNING"])
                return
            self._close_statement_window()
            self._save_stage3_files(text)
            prompt_box.configure(state="disabled")
            send_button.configure(state="disabled", text="Generando respuesta...")
            status_label.configure(
                text="🤖  Generando una respuesta aislada y preparando las preguntas "
                     "(puede tardar uno o dos minutos)...",
                text_color=self.c["TEXT_MUTED"],
            )
            threading.Thread(target=self._run_isolated_prompt, args=(text,), daemon=True).start()

        send_button.configure(command=on_send)

    def _save_stage3_files(self, prompt_text: str):
        """Guarda lo escrito en la Etapa 3 (prompt libre + registro de
        aperturas del enunciado) y, igual que las etapas 2/4/5 (ver
        _export_stage), el recorte de NeuroSky/Emotion/Eye de esta etapa --
        la frecuencia cardiaca se corta despues, al cargar el reloj (ver
        _snapshot_pending_heart_rate)."""
        participant = self.app.store.get_active()
        window = self._stage_timer.finish(3)
        if participant is None:
            return
        challenge_number = self.game_index + 1
        folder = stage_dir(participant, challenge_number, 3, attempt=self._attempt_number)
        write_stage3_files(folder, prompt_text, self._statement_log)
        warnings, sync_sources = self._write_stage_sensors(participant, folder, window)
        sync_sources["enunciado_aperturas"] = {"count": len(self._statement_log)}
        write_sync_timeline(folder, window, sync_sources)
        if warnings:
            self._stage_warnings[3] = warnings

    def _run_isolated_prompt(self, participant_prompt: str):
        try:
            result = generate_isolated_response(self.current_challenge, participant_prompt)
        except Exception as exc:  # el hilo de fondo no debe tumbar la app
            result = ChallengeSolveResult(ok=False, error=str(exc))
        self.app.after(0, lambda: self._show_stage4(result))

    # ---------------- Etapa 4 ----------------
    def _show_stage4(self, result: ChallengeSolveResult):
        self._clear()
        self._close_statement_window()
        self.current_result = result
        challenge = self.current_challenge
        self._stage_timer.start(4)

        self._header(self.container, "ETAPA 4 DE 6 · RESULTADO", challenge.title)
        self._exit_button(self.container)
        self._render_pending_warnings(self.container)

        left, right, buttons_row = self._split_columns(self.container)

        if result.ok:
            pill_text, pill_bg, pill_fg = "✅  La IA respondió", "#1c3a26", "#4ade80"
        else:
            pill_text, pill_bg, pill_fg = "❌  No se pudo generar una respuesta", "#3a1c1e", "#f87171"
        ctk.CTkLabel(
            left, text=pill_text, font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12), weight="bold"),
            fg_color=pill_bg, text_color=pill_fg, corner_radius=10, padx=12, pady=4,
        ).pack(anchor="w", pady=(0, 10))

        if result.error:
            ctk.CTkLabel(
                left, text=result.error, font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12)),
                text_color="#f87171", wraplength=wrap(420), justify="left",
            ).pack(anchor="w", pady=(0, 10))

        self._section(left, "💻  Código generado (sin ningún contexto)")
        ctk.CTkLabel(
            left,
            text="Recuerda: esta IA solo vio el prompt exacto que escribiste en la Etapa 3, "
            "nada más.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(11)), text_color=self.c["TEXT_MUTED"],
            wraplength=wrap(420), justify="left",
        ).pack(anchor="w", pady=(0, 8))
        self._code_block(left, result.response_text or "(sin respuesta para mostrar)")

        self._build_quiz(
            right, result.comprehension_questions, self.stage3_answers,
            title="📝  Preguntas sobre la respuesta",
            generation_error=result.quiz_generation_error,
        )

        def on_retry():
            self._attempt_number += 1
            self._show_stage3()

        def on_continue():
            self._save_answers("etapa3_comprension", result.comprehension_questions, self.stage3_answers)
            self._export_stage(4, result.comprehension_questions, self._answers_as_ints(self.stage3_answers))
            self._show_stage5()

        ctk.CTkButton(
            buttons_row, text="🔁  Reintentar este desafío", height=scaled(42), corner_radius=10,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(13)),
            fg_color=self.c["BG_CARD_ALT"], hover_color=self.c["BORDER"],
            command=on_retry,
        ).pack(side="left", padx=(0, 8))
        continue_button = ctk.CTkButton(
            buttons_row, text="Continuar a Etapa 5 · Razonamiento  ▶", height=scaled(42), corner_radius=10,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(13), weight="bold"),
            fg_color=self.c["ACCENT"], hover_color=self.c["ACCENT_HOVER"],
            command=on_continue,
        )
        continue_button.pack(side="left")
        self._require_all_answered(continue_button, self.stage3_answers)

    # ---------------- Etapa 5 ----------------
    def _show_stage5(self):
        self._clear()
        result = self.current_result
        challenge = self.current_challenge
        self._stage_timer.start(5)

        self._header(self.container, "ETAPA 5 DE 6 · RAZONAMIENTO", challenge.title)
        self._exit_button(self.container)
        self._render_pending_warnings(self.container)

        left, right, buttons_row = self._split_columns(self.container)

        self._section(left, "💻  Código generado (referencia)")
        self._code_block(left, result.response_text if result else "(sin respuesta para mostrar)")

        self._section(left, "🧭  ¿Resuelve el desafío? Análisis de la solución")
        quiz_error = result.quiz_generation_error if result else ""
        explanation_text = (result.reasoning_explanation if result else "") or (
            f"No se generó una explicación para este caso. ({quiz_error})" if quiz_error
            else "No se generó una explicación para este caso."
        )
        ctk.CTkLabel(
            left, text=explanation_text,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(14)),
            wraplength=wrap(420), justify="left", anchor="w",
        ).pack(anchor="w", fill="x", pady=(0, 18))

        self._build_quiz(
            right, result.reasoning_questions if result else [], self.stage4_answers,
            title="🧠  Preguntas de razonamiento", generation_error=quiz_error,
        )

        def on_retry():
            self._attempt_number += 1
            self._show_stage3()

        def on_continue():
            questions = result.reasoning_questions if result else []
            self._save_answers("etapa4_razonamiento", questions, self.stage4_answers)
            self._export_stage(5, questions, self._answers_as_ints(self.stage4_answers))
            self._snapshot_pending_heart_rate()
            self._show_stage6()

        ctk.CTkButton(
            buttons_row, text="🔁  Reintentar este desafío", height=scaled(42), corner_radius=10,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(13)),
            fg_color=self.c["BG_CARD_ALT"], hover_color=self.c["BORDER"],
            command=on_retry,
        ).pack(side="left", padx=(0, 8))
        continue_button = ctk.CTkButton(
            buttons_row, text="Continuar a Etapa 6 · Ver la solución en acción  ▶", height=scaled(42), corner_radius=10,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(13), weight="bold"),
            fg_color=self.c["ACCENT"], hover_color=self.c["ACCENT_HOVER"],
            command=on_continue,
        )
        continue_button.pack(side="left")
        self._require_all_answered(continue_button, self.stage4_answers)

    # ---------------- Etapa 6 ----------------
    def _show_stage6(self):
        self._clear()
        result = self.current_result
        challenge = self.current_challenge
        game = self.current_game
        is_last = self.game_index >= len(GUIDED_SESSION_GAME_ORDER) - 1

        self._header(self.container, "ETAPA 6 DE 6 · SOLUCIÓN EN ACCIÓN", challenge.title)
        self._exit_button(self.container)
        self._render_pending_warnings(self.container)

        body = ctk.CTkFrame(self.container, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=36, pady=(10, 20))
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(body, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")

        ctk.CTkLabel(
            scroll,
            text=(
                "Ahora se aplica, sobre el juego real, exactamente el código que "
                "generó la IA a partir de tu prompt en la Etapa 3 -- así puedes ver "
                "en acción esa solución concreta, con sus aciertos y sus errores. "
                "El juego se abre en pantalla completa -- presiona ESC para salir "
                "de él cuando termines de probarlo, y continúa."
            ),
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(13)), text_color=self.c["TEXT_MUTED"],
            wraplength=wrap(900), justify="left",
        ).pack(anchor="w", pady=(0, 14))

        self._section(scroll, "💻  Código aplicado")
        self._code_block(scroll, result.response_text if result and result.ok else "(sin código para aplicar)")

        if result and result.ok and result.response_text:
            self._play_button(
                scroll, "🎮  Jugar con esta solución",
                lambda: launch_game_with_solution(game, challenge, result.response_text),
            )
        else:
            ctk.CTkLabel(
                scroll,
                text="No hay una respuesta válida de la Etapa 3 para aplicar al juego.",
                font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12)), text_color=self.c["WARNING"],
                wraplength=wrap(900), justify="left",
            ).pack(anchor="w", pady=(0, 12))

        buttons_row = ctk.CTkFrame(body, fg_color="transparent")
        buttons_row.grid(row=1, column=0, sticky="ew", pady=(14, 0))

        def on_retry():
            self._attempt_number += 1
            self._show_stage3()

        def on_next_game():
            # Sigue de largo al siguiente desafío sin cortar nada -- los
            # sensores (NeuroSky/Camera Tracker) siguen leyendo en vivo
            # igual que antes, sin pasar por la pantalla del reloj.
            self._advance_or_finish()

        def on_finish_session():
            # Último desafío: no hay "siguiente juego" al que seguir
            # leyendo, así que sí corresponde pedir la carpeta del reloj
            # antes de cerrar la sesión -- salvo que el reloj no se haya
            # habilitado para esta sesión (ver self._enabled_devices).
            self._show_heart_rate_import_or_skip(self._advance_or_finish)

        def on_save_progress():
            # Acá el evaluador corta la sesión a propósito -- es el punto
            # donde tiene sentido pedir la carpeta del reloj de este
            # desafío antes de guardar el progreso y salir.
            def after_finish():
                self._save_progress(self.game_index + 1)
                messagebox.showinfo(
                    "Progreso guardado",
                    "Guardamos tu progreso. La próxima vez que entres a la sesión\n"
                    "guiada vas a retomar en el siguiente desafío.",
                    parent=self.app,
                )
                self._exit_guided_session()
            self._show_heart_rate_import_or_skip(after_finish)

        ctk.CTkButton(
            buttons_row, text="🔁  Reintentar este desafío", height=scaled(42), corner_radius=10,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(13)),
            fg_color=self.c["BG_CARD_ALT"], hover_color=self.c["BORDER"],
            command=on_retry,
        ).pack(side="left", padx=(0, 8))

        if is_last:
            ctk.CTkButton(
                buttons_row, text="🏁  Terminar sesión guiada", height=scaled(42), corner_radius=10,
                font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(13), weight="bold"),
                fg_color=self.c["ACCENT"], hover_color=self.c["ACCENT_HOVER"],
                command=on_finish_session,
            ).pack(side="left")
        else:
            ctk.CTkButton(
                buttons_row, text="Siguiente juego  ▶", height=scaled(42), corner_radius=10,
                font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(13), weight="bold"),
                fg_color=self.c["ACCENT"], hover_color=self.c["ACCENT_HOVER"],
                command=on_next_game,
            ).pack(side="left", padx=(0, 8))
            ctk.CTkButton(
                buttons_row, text="💾  Guardar progreso", height=scaled(42), corner_radius=10,
                font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(13)),
                fg_color=self.c["BG_CARD_ALT"], hover_color=self.c["BORDER"],
                command=on_save_progress,
            ).pack(side="left")

    # ---------------- Importar reloj + cierre del desafío ----------------
    def _show_heart_rate_import_or_skip(self, on_done):
        """Si el reloj no esta habilitado para esta sesion (ver
        self._enabled_devices / App._ask_session_devices), cierra el
        desafio directo sin mostrar la pantalla de importacion -- no tiene
        sentido pedir un dato de un dispositivo que el evaluador ya dijo
        que no se iba a usar."""
        if "heart_rate" in self._enabled_devices:
            self._show_heart_rate_import(on_done)
        else:
            self._finish_challenge(None, on_done)

    def _show_heart_rate_import(self, on_done):
        """Pantalla entre la Etapa 6 y el cierre del desafío: el export del
        reloj recien existe despues de terminar el desafio (el evaluador lo
        genera ahi), asi que no tiene sentido mezclarlo con la Etapa 6.

        "Siguiente juego" NO pasa por acá -- los sensores siguen leyendo en
        vivo sin cortes y el evaluador puede no tener el export del reloj
        listo todavía. Esta pantalla solo aparece en los dos puntos donde
        el evaluador corta a propósito: "Guardar progreso" (a mitad de
        sesión) y "Terminar sesión guiada" (en el último desafío, donde no
        hay un "siguiente juego" al que seguir leyendo). `on_done` decide
        que pasa despues de cerrar el desafío (ver _show_stage6)."""
        self._clear()
        challenge_number = self.game_index + 1
        self._header(self.container, "IMPORTAR RELOJ", f"Desafío {challenge_number} · Frecuencia cardíaca")
        self._exit_button(self.container)
        self._render_pending_warnings(self.container)

        body = ctk.CTkFrame(self.container, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=36, pady=(10, 20))

        accepted_folder: dict = {"value": None}

        def on_folder_accepted(path):
            accepted_folder["value"] = path
            continue_button.configure(state="normal")

        HeartRateDropFrame(
            body, self.c, FONT_FAMILY, scaled, wrap, on_folder_accepted,
        ).pack(fill="x", pady=(0, 16))

        buttons_row = ctk.CTkFrame(body, fg_color="transparent")
        buttons_row.pack(fill="x")

        def on_continue():
            self._finish_challenge(accepted_folder["value"], on_done)

        def on_skip():
            self._finish_challenge(None, on_done)

        continue_button = ctk.CTkButton(
            buttons_row, text="Continuar  ▶", height=scaled(42), corner_radius=10,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(13), weight="bold"),
            fg_color=self.c["ACCENT"], hover_color=self.c["ACCENT_HOVER"],
            state="disabled", command=on_continue,
        )
        continue_button.pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            buttons_row, text="Saltar por ahora", height=scaled(42), corner_radius=10,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(13)),
            fg_color=self.c["BG_CARD_ALT"], hover_color=self.c["BORDER"],
            command=on_skip,
        ).pack(side="left")

    def _snapshot_pending_heart_rate(self):
        """Guarda, para el desafío actual, las carpetas/ventanas de las
        etapas 2/3/4/5 tal como están AHORA, en una cola a procesar cuando
        finalmente aparezca la pantalla de importar el reloj.

        Por que hace falta: self._stage_timer solo guarda UNA ventana por
        número de etapa (se pisa al arrancar el siguiente desafío, ver
        StageTimer.start), y esa pantalla NO aparece después de cada
        desafío -- "Siguiente juego" sigue de largo sin cortar los
        sensores, recién se pide el reloj en "Guardar progreso" o
        "Terminar sesión guiada" (ver _show_heart_rate_import). Sin este
        snapshot tomado al toque de terminar la Etapa 5 (ver on_continue
        más arriba), un solo export del reloj entregado al final de una
        sesión de varios desafíos solo alcanzaba a recortarle la
        frecuencia cardíaca al ÚLTIMO -- los anteriores quedaban con la
        etapa 2/3/4/5 ya exportada (NeuroSky/Emotion/Eye) pero sin
        heart_rate.csv, porque su ventana ya se habia perdido para cuando
        se pedia el reloj."""
        participant = self.app.store.get_active()
        if participant is None or self.current_game is None:
            return
        challenge_number = self.game_index + 1
        already_queued = any(
            entry["challenge_number"] == challenge_number and entry["attempt"] == self._attempt_number
            for entry in self._pending_heart_rate_challenges
        )
        if already_queued:
            return
        self._pending_heart_rate_challenges.append({
            "challenge_number": challenge_number,
            "attempt": self._attempt_number,
            "challenge_folder": challenge_dir(participant, challenge_number),
            "stage_folders": {
                2: stage_dir(participant, challenge_number, 2),
                3: stage_dir(participant, challenge_number, 3, attempt=self._attempt_number),
                4: stage_dir(participant, challenge_number, 4, attempt=self._attempt_number),
                5: stage_dir(participant, challenge_number, 5, attempt=self._attempt_number),
            },
            "stage_windows": {
                2: self._stage_timer.window(2),
                3: self._stage_timer.window(3),
                4: self._stage_timer.window(4),
                5: self._stage_timer.window(5),
            },
        })

    def _finish_challenge(self, heart_rate_export_folder: Optional[Path], on_done):
        """Recorta (si se cargó) la frecuencia cardíaca del reloj en las
        etapas 2/3/4/5 de TODOS los desafíos acumulados desde la última vez
        que se pidió el reloj (ver _pending_heart_rate_challenges /
        _snapshot_pending_heart_rate) -- no solo el desafío actual, porque
        "Siguiente juego" puede haber encadenado varios sin pasar por acá.
        El resto de los datos (sensores, cuestionarios, prompt, enunciado)
        ya se guardaron incrementalmente en cada etapa (ver _export_stage /
        _save_stage3_files), así que esto no los vuelve a tocar. Al
        terminar llama a `on_done` (ver _show_heart_rate_import) en vez de
        avanzar directo -- el llamador decide qué sigue."""
        self._snapshot_pending_heart_rate()  # por si se corta antes de llegar a la Etapa 5
        pending = self._pending_heart_rate_challenges
        self._pending_heart_rate_challenges = []

        participant = self.app.store.get_active()
        if participant is None or not pending:
            on_done()
            return

        warnings_by_challenge: dict[int, dict[int, list[str]]] = {}
        if heart_rate_export_folder is not None:
            for entry in pending:
                warnings_by_stage = import_heart_rate_for_challenge(
                    heart_rate_export_folder, entry["challenge_folder"],
                    entry["stage_folders"], entry["stage_windows"],
                )
                merged = warnings_by_challenge.setdefault(entry["challenge_number"], {})
                for stage, warnings in warnings_by_stage.items():
                    if warnings:
                        merged[stage] = warnings

        written_challenges = set()
        for entry in pending:
            challenge_number = entry["challenge_number"]
            if challenge_number in written_challenges:
                continue  # ya se escribio el manifiesto (con TODOS los intentos) mas abajo
            written_challenges.add(challenge_number)

            stage_status: dict = {}
            if heart_rate_export_folder is not None:
                stage_status["heart_rate_warnings"] = {
                    str(stage): warnings for stage, warnings in warnings_by_challenge.get(challenge_number, {}).items()
                }
            elif "heart_rate" not in self._enabled_devices:
                stage_status["heart_rate"] = "dispositivo no habilitado para esta sesión"
            else:
                stage_status["heart_rate"] = "omitido por el evaluador"
            write_challenge_manifest(entry["challenge_folder"], participant, challenge_number, stage_status)
        on_done()

    def _advance_or_finish(self):
        participant = self.app.store.get_active()
        self.game_index += 1
        if self.game_index >= len(GUIDED_SESSION_GAME_ORDER):
            self._session_completed = True
            self._clear_progress()
            if participant is not None:
                completed = available_challenges(participant_session_dir(participant))
                write_session_index(participant_session_dir(participant), completed)
            self._exit_guided_session()
            return
        self._start_current_game()
