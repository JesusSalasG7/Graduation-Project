"""Prueba suelta de los sensores, sin entrar a una sesión guiada.

Abre una ventana aparte por dispositivo (NeuroSky o Cámara con Emotion +
Eye Tracker) con el estado y la salida en vivo, para revisar que todo
anda antes de sentar a un participante. Usa los mismos lanzadores que la
sesión guiada (sensors/), pero NO graba nada a nombre de un participante:

- NeuroSky: graba en su propio CSV (NEUROSKY_PROBE_FILE), que se borra
  al cerrar la ventana -- así nunca pisa test_neurodata.csv, el de la
  sesión.
- Cámara: se lanza sin participante, así que camera_tracker.py no
  escribe ningún CSV.

Antes de entrar a una sesión guiada hay que llamar a stop_all(): la
cámara solo admite un proceso a la vez y el NeuroSky un solo lector.
"""

import signal
import subprocess
import threading
import time
from typing import Callable, Optional

import customtkinter as ctk

from sensors.camera_tracker_launcher import run_calibration, start_camera_tracker
from sensors.neurosky_launcher import (
    NEUROSKY_DIR,
    RFCOMM_DEVICE,
    bind_neurosky,
    release_neurosky,
    start_neurosky_test,
    sudo_needs_password,
)
from ui.monitors import SLOT_GAZE, SLOT_VIDEO, researcher_layout

NEUROSKY_PROBE_FILE = NEUROSKY_DIR / "prueba_neurodata.csv"
NEUROSKY_STALE_SECONDS = 10


def _stop_process(process: Optional[subprocess.Popen]) -> None:
    # SIGINT (como un Ctrl+C) para que los scripts cierren prolijos.
    if process is None or process.poll() is not None:
        return
    try:
        process.send_signal(signal.SIGINT)
        process.wait(timeout=3)
    except Exception:
        process.terminate()


class _TestWindow:
    """Ventana con título, estado, una fila de botones y una terminal."""

    def __init__(self, tester: "DeviceTester", title: str, heading: str, on_close: Callable[[], None]):
        c, font, scaled = tester.c, tester.font_family, tester.scaled
        self.app = tester.app
        self.c = c
        self.font_family = font
        self.scaled = scaled
        self.window = ctk.CTkToplevel(self.app)
        self.window.title(title)
        self.window.geometry(f"{scaled(480)}x{scaled(340)}")
        self.window.configure(fg_color=c["BG_CARD"])
        self.window.transient(self.app)

        ctk.CTkLabel(
            self.window, text=heading, font=ctk.CTkFont(family=font, size=scaled(15), weight="bold"),
        ).pack(anchor="w", padx=16, pady=(16, 4))
        ctk.CTkLabel(
            self.window, text="Modo prueba: no se guarda nada a nombre de ningún participante.",
            font=ctk.CTkFont(family=font, size=scaled(11)), text_color=c["TEXT_MUTED"], anchor="w",
        ).pack(anchor="w", padx=16, pady=(0, 6))

        self.status_label = ctk.CTkLabel(
            self.window, text="", font=ctk.CTkFont(family=font, size=scaled(12)),
            text_color=c["TEXT_MUTED"], anchor="w", justify="left",
        )
        self.status_label.pack(anchor="w", fill="x", padx=16, pady=(0, 6))

        self.buttons_row = ctk.CTkFrame(self.window, fg_color="transparent")
        self.buttons_row.pack(anchor="w", fill="x", padx=16, pady=(0, 8))

        self.terminal = ctk.CTkTextbox(
            self.window, fg_color=c["BG_CARD_ALT"], wrap="word",
            font=ctk.CTkFont(family="monospace", size=scaled(12)),
        )
        self.terminal.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.terminal.configure(state="disabled")

        self.alive = True
        self.window.protocol("WM_DELETE_WINDOW", on_close)

    def button(self, text: str, command, primary: bool = False) -> ctk.CTkButton:
        button = ctk.CTkButton(
            self.buttons_row, text=text, height=self.scaled(34), corner_radius=8,
            font=ctk.CTkFont(family=self.font_family, size=self.scaled(12), weight="bold" if primary else "normal"),
            fg_color=self.c["ACCENT"] if primary else self.c["BG_CARD_ALT"],
            hover_color=self.c["ACCENT_HOVER"] if primary else self.c["BORDER"],
            command=command,
        )
        button.pack(side="left", padx=(0, 8))
        return button

    # Los métodos de abajo se pueden llamar desde hilos de fondo: todo
    # pasa por app.after para tocar los widgets solo desde el hilo de Tk.
    def _on_tk(self, fn):
        def do():
            if not self.alive:
                return
            try:
                fn()
            except Exception:
                pass
        self.app.after(0, do)

    def log(self, line: str):
        def do():
            self.terminal.configure(state="normal")
            self.terminal.insert("end", line + "\n")
            self.terminal.see("end")
            self.terminal.configure(state="disabled")
        self._on_tk(do)

    def clear_log(self):
        def do():
            self.terminal.configure(state="normal")
            self.terminal.delete("1.0", "end")
            self.terminal.configure(state="disabled")
        self._on_tk(do)

    def status(self, text: str, color: Optional[str] = None):
        self._on_tk(lambda: self.status_label.configure(text=text, text_color=color or self.c["TEXT_MUTED"]))

    def set_enabled(self, button: ctk.CTkButton, enabled: bool):
        self._on_tk(lambda: button.configure(state="normal" if enabled else "disabled"))

    def destroy(self):
        self.alive = False
        try:
            self.window.destroy()
        except Exception:
            pass


class DeviceTester:
    def __init__(self, app, colors: dict, font_family: str, scaled, ask_password: Callable[[], Optional[str]]):
        """`ask_password` muestra el modal de contraseña de sudo y bloquea
        al hilo que lo llama (ver SessionWizard._ask_sudo_password_blocking)."""
        self.app = app
        self.c = colors
        self.font_family = font_family
        self.scaled = scaled
        self.ask_password = ask_password

        self._neurosky_win: Optional[_TestWindow] = None
        self._neurosky_process: Optional[subprocess.Popen] = None
        self._neurosky_busy = False
        self._neurosky_last_data_at: Optional[float] = None

        self._camera_win: Optional[_TestWindow] = None
        self._camera_process: Optional[subprocess.Popen] = None
        self._camera_busy = False

    def is_running(self) -> bool:
        return self._neurosky_win is not None or self._camera_win is not None

    def stop_all(self, wait: bool = False):
        """Corta las dos pruebas y cierra sus ventanas. Con `wait` espera
        a que los procesos terminen (unos segundos como mucho) -- hace
        falta al cerrar la app, para no dejarlos huérfanos."""
        self._close_neurosky(wait)
        self._close_camera(wait)

    # ---------------- NeuroSky ----------------
    def open_neurosky(self):
        if self._neurosky_win is not None:
            self._neurosky_win.window.lift()
            return
        win = _TestWindow(self, "Probar NeuroSky", "🧠  Prueba del NeuroSky", self._close_neurosky)
        self._neurosky_retry = win.button("🔄  Conectar de nuevo", self._start_neurosky_thread)
        self._neurosky_win = win
        self._start_neurosky_thread()
        self.app.after(5000, self._neurosky_watchdog)

    def _start_neurosky_thread(self):
        if self._neurosky_busy:
            return
        self._neurosky_busy = True
        threading.Thread(target=self._run_neurosky, daemon=True).start()

    def _run_neurosky(self):
        win = self._neurosky_win
        try:
            if win is None:
                return
            _stop_process(self._neurosky_process)
            self._neurosky_process = None
            win.set_enabled(self._neurosky_retry, False)

            password = None
            if sudo_needs_password():
                win.status("Esperando la contraseña de administrador...")
                password = self.ask_password()
                if password is None:
                    win.status("Se canceló la contraseña -- no se pudo vincular.", self.c["WARNING"])
                    win.set_enabled(self._neurosky_retry, True)
                    return

            win.status("Vinculando el dispositivo por bluetooth...")
            if not bind_neurosky(win.log, password=password):
                win.status("No se pudo vincular -- revisa que esté encendido.", self.c["WARNING"])
                win.set_enabled(self._neurosky_retry, True)
                return
            win.log(f"[OK] Vinculación bluetooth lista en {RFCOMM_DEVICE}.")
            win.status("Iniciando lectura de señales...")

            try:
                process = start_neurosky_test(NEUROSKY_PROBE_FILE)
            except Exception as exc:
                win.log(f"[ERROR] {exc}")
                win.status("No se pudo iniciar test_neurosky.py.", self.c["WARNING"])
                win.set_enabled(self._neurosky_retry, True)
                return

            if self._neurosky_win is not win:  # se cerró la ventana mientras conectaba
                _stop_process(process)
                return
            self._neurosky_process = process
            self._neurosky_last_data_at = time.monotonic()
        finally:
            self._neurosky_busy = False

        win.set_enabled(self._neurosky_retry, True)
        for raw in process.stdout:
            self._on_neurosky_line(win, raw.rstrip())
        returncode = process.wait()
        if self._neurosky_process is process:
            self._neurosky_process = None
            if returncode != 0:
                win.log(f"[ERROR] test_neurosky.py terminó con código {returncode}.")
                win.status("Se perdió la conexión -- enciéndelo y toca Conectar de nuevo.", self.c["WARNING"])

    def _on_neurosky_line(self, win: _TestWindow, line: str):
        win.log(line)
        self._neurosky_last_data_at = time.monotonic()
        lower = line.lower()
        if "[error]" in lower:
            win.status("⚠️  Error -- revisa que el dispositivo esté encendido y con batería.", self.c["WARNING"])
        elif "[contacto ok]" in lower:
            win.status("🟢  Señal OK -- recibiendo datos del NeuroSky.")
        elif "[ajustando" in lower:
            win.status("🟡  Contacto detectado, ajustando la señal...")
        elif "[sin contacto" in lower:
            win.status("🔴  Sin contacto -- revisa la posición del sensor.")

    def _neurosky_watchdog(self):
        win = self._neurosky_win
        if win is None:
            return
        process = self._neurosky_process
        if process is not None and process.poll() is None and self._neurosky_last_data_at is not None:
            elapsed = time.monotonic() - self._neurosky_last_data_at
            if elapsed > NEUROSKY_STALE_SECONDS:
                win.status(f"⚠️  Sin señal hace {int(elapsed)}s -- revisa el dispositivo.", self.c["WARNING"])
        self.app.after(5000, self._neurosky_watchdog)

    def _close_neurosky(self, wait: bool = False):
        win = self._neurosky_win
        if win is None:
            return
        self._neurosky_win = None
        process = self._neurosky_process
        self._neurosky_process = None
        win.destroy()

        def cleanup():
            _stop_process(process)
            try:
                NEUROSKY_PROBE_FILE.unlink()
            except FileNotFoundError:
                pass
            # Se libera el rfcomm solo si sudo no pide contraseña (credencial
            # cacheada del bind); si no, queda vinculado, y la sesión guiada
            # ya sabe saltarse el bind cuando /dev/rfcomm0 existe.
            if not sudo_needs_password():
                release_neurosky(lambda _line: None)
        if wait:
            cleanup()
        else:
            threading.Thread(target=cleanup, daemon=True).start()

    # ---------------- Cámara (Emotion + Eye Tracker) ----------------
    def open_camera(self):
        if self._camera_win is not None:
            self._camera_win.window.lift()
            return
        win = _TestWindow(
            self, "Probar Cámara", "📷  Prueba de la Cámara (Emotion + Eye Tracker)", self._close_camera,
        )
        self._camera_calibrate_btn = win.button(
            "🎯  Calibrar y probar", lambda: self._start_camera_thread(calibrate=True), primary=True,
        )
        self._camera_quick_btn = win.button(
            "▶  Probar sin calibrar", lambda: self._start_camera_thread(calibrate=False),
        )
        self._camera_stop_btn = win.button("⏹  Detener", self._stop_camera)
        self._camera_stop_btn.configure(state="disabled")
        win.status(
            "\"Calibrar y probar\" pide mirar a la izquierda y a la derecha, igual que en la sesión. "
            "\"Probar sin calibrar\" arranca directo con el corte izquierda/derecha por defecto.",
        )
        self._camera_win = win

    def _set_camera_buttons(self, running: bool, busy: bool = False):
        win = self._camera_win
        if win is None:
            return
        win.set_enabled(self._camera_calibrate_btn, not busy)
        win.set_enabled(self._camera_quick_btn, not busy)
        win.set_enabled(self._camera_stop_btn, running and not busy)

    def _start_camera_thread(self, calibrate: bool):
        if self._camera_busy:
            return
        self._camera_busy = True
        threading.Thread(target=self._run_camera, args=(calibrate,), daemon=True).start()

    def _run_camera(self, calibrate: bool):
        win = self._camera_win
        try:
            if win is None:
                return
            _stop_process(self._camera_process)
            self._camera_process = None
            self._set_camera_buttons(running=False, busy=True)
            win.clear_log()

            left_x = right_x = None
            if calibrate:
                win.status("🎯  Calibrando -- mira la ventana de la cámara que se abrió aparte...")
                try:
                    left_x, right_x = run_calibration(win.log, mirror=True)
                except Exception as exc:
                    win.status(f"⚠️  No se pudo calibrar: {exc}", self.c["WARNING"])
                    self._set_camera_buttons(running=False)
                    return

            win.status("Iniciando el seguimiento...")
            try:
                layout = researcher_layout(self.app)
                # Sin participante: camera_tracker.py no graba ningún CSV.
                process = start_camera_tracker(
                    None, "prueba", left_x, right_x,
                    video_geometry=layout[SLOT_VIDEO], gaze_geometry=layout[SLOT_GAZE],
                )
            except Exception as exc:
                win.status(f"⚠️  No se pudo iniciar la cámara: {exc}", self.c["WARNING"])
                self._set_camera_buttons(running=False)
                return

            if self._camera_win is not win:  # se cerró la ventana mientras calibraba
                _stop_process(process)
                return
            self._camera_process = process
            if calibrate:
                win.status(f"🟢  Corriendo (izquierda={left_x:.2f}, derecha={right_x:.2f}).")
            else:
                win.status("🟢  Corriendo sin calibrar (corte izquierda/derecha por defecto).")
            self._set_camera_buttons(running=True)
        finally:
            self._camera_busy = False

        for raw in process.stdout:
            win.log(raw.rstrip())
        process.wait()
        if self._camera_process is process:
            self._camera_process = None
            win.status("El Camera Tracker se cerró.", self.c["WARNING"])
            self._set_camera_buttons(running=False)

    def _stop_camera(self):
        process = self._camera_process
        self._camera_process = None
        threading.Thread(target=_stop_process, args=(process,), daemon=True).start()
        if self._camera_win is not None:
            self._camera_win.status("Detenido.")
        self._set_camera_buttons(running=False)

    def _close_camera(self, wait: bool = False):
        win = self._camera_win
        if win is None:
            return
        self._camera_win = None
        process = self._camera_process
        self._camera_process = None
        win.destroy()
        if wait:
            _stop_process(process)
        else:
            threading.Thread(target=_stop_process, args=(process,), daemon=True).start()
