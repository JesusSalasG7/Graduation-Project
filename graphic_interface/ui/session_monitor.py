"""Ventana "Sesión en curso" para el investigador: el tiempo total del
participante en la sesión guiada (acumulado entre sesiones, ver
storage/session_timing.py), cuánto lleva la sesión actual, en qué
desafío/juego y en qué etapa está, y cuánto lleva en esa etapa.

El cronómetro arranca con el juego (la Etapa 1 del primer desafío que se
juega en esta sesión); si el participante retoma una sesión guardada,
el total sigue desde donde quedó. "Guardar progreso" o "Terminar sesión
guiada" lo pausan.

Se abre en el monitor del investigador (ver monitors.py) junto a las
ventanas del NeuroSky y de la cámara, siempre visible, y no es hija del
frame de la sesión guiada, así que no se borra al cambiar de etapa. Al
salir de la sesión queda abierta con los tiempos finales hasta que el
investigador la cierra (o empieza otra sesión).
"""

import time
from typing import Optional

import customtkinter as ctk

from storage.session_timing import format_duration
from ui.monitors import corner_position, researcher_monitor

FONT_FAMILY = "Segoe UI"


class SessionMonitorWindow:
    def __init__(
        self, app, colors: dict, scaled, wrap, participant_text: str,
        previous_total_s: float = 0, session_number: int = 1,
    ):
        self.app = app
        self.c = colors
        self._previous_total_s = previous_total_s
        self._session_number = session_number
        self._session_started_at: Optional[float] = None
        self._stage_started_at: Optional[float] = None
        self._stopped_at: Optional[float] = None
        self._tick_job = None

        window = ctk.CTkToplevel(app)
        window.title("Sesión en curso")
        win_w, win_h = wrap(540), wrap(260)
        x, y = corner_position(researcher_monitor(app), "top-left", win_w, win_h)
        window.geometry(f"{win_w}x{win_h}+{x}+{y}")
        window.configure(fg_color=colors["BG_CARD"])
        # Mismo motivo que las ventanas del NeuroSky y la cámara: la sesión
        # guiada corre en pantalla completa y la taparía.
        window.attributes("-topmost", True)
        window.protocol("WM_DELETE_WINDOW", self.close)

        ctk.CTkLabel(
            window, text=f"⏱️  Tiempo total · {participant_text}",
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(13), weight="bold"),
        ).pack(anchor="w", padx=16, pady=(14, 0))
        self._total_label = ctk.CTkLabel(
            window, text=format_duration(previous_total_s),
            font=ctk.CTkFont(family="monospace", size=scaled(30), weight="bold"),
            text_color=colors["TEXT_MUTED"],
        )
        self._total_label.pack(anchor="w", padx=16)
        self._session_label = ctk.CTkLabel(
            window, text="", font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(11)),
            text_color=colors["TEXT_MUTED"], anchor="w",
        )
        self._session_label.pack(anchor="w", fill="x", padx=16)
        self._challenge_label = ctk.CTkLabel(
            window, text="El cronómetro arranca al iniciar el juego.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12)), anchor="w", justify="left",
            wraplength=win_w - 32,
        )
        self._challenge_label.pack(anchor="w", fill="x", padx=16)
        self._stage_label = ctk.CTkLabel(
            window, text="", font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12), weight="bold"),
            text_color=colors["ACCENT"], anchor="w", justify="left", wraplength=win_w - 32,
        )
        self._stage_label.pack(anchor="w", fill="x", padx=16)
        self._stage_time_label = ctk.CTkLabel(
            window, text="", font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(11)),
            text_color=colors["TEXT_MUTED"], anchor="w",
        )
        self._stage_time_label.pack(anchor="w", fill="x", padx=16, pady=(0, 12))

        self.window: Optional[ctk.CTkToplevel] = window
        self._tick()

    def _session_text(self) -> str:
        text = f"Sesión {self._session_number}"
        if self._session_number > 1:
            resumed = self._session_number - 1
            text += f" (retomada {resumed} {'vez' if resumed == 1 else 'veces'})"
        return text

    def set_position(self, challenge_text: str, stage_text: str, starts_session: bool = False):
        """Actualiza desafío/etapa y reinicia el tiempo de la etapa.
        `starts_session` arranca el cronómetro (solo la primera vez).
        Con el cronómetro pausado solo cambia el texto."""
        if self.window is None:
            return
        self._challenge_label.configure(text=challenge_text)
        self._stage_label.configure(text=stage_text)
        if self._stopped_at is not None:
            return
        now = time.monotonic()
        if starts_session and self._session_started_at is None:
            self._session_started_at = now
            self._total_label.configure(text_color="white")
        if self._session_started_at is not None:
            self._stage_started_at = now
        self._tick(reschedule=False)

    def pause(self, reason: str):
        """Detiene el cronómetro ("Guardar progreso"/"Terminar sesión")."""
        if self.window is None or self._stopped_at is not None:
            return
        self._stopped_at = time.monotonic()
        self._tick(reschedule=False)
        self._total_label.configure(text_color=self.c["WARNING"])
        self._stage_time_label.configure(text=f"⏸  En pausa · {reason}")

    def finish(self):
        """Fin de la sesión guiada: deja la ventana con los tiempos finales."""
        if self.window is None:
            return
        if self._stopped_at is None:
            self.pause("sesión cerrada")
        self.window.title("Sesión terminada")
        self._stage_label.configure(text="Sesión terminada", text_color=self.c["TEXT_MUTED"])
        if self._session_started_at is None:
            self._stage_time_label.configure(text="No se llegó a iniciar un juego en esta sesión.")
        if self._tick_job is not None:
            self.app.after_cancel(self._tick_job)
            self._tick_job = None

    def close(self):
        if self._tick_job is not None:
            self.app.after_cancel(self._tick_job)
            self._tick_job = None
        window, self.window = self.window, None
        if window is not None:
            try:
                window.destroy()
            except Exception:
                pass

    def _tick(self, reschedule: bool = True):
        if self.window is None:
            return
        now = self._stopped_at or time.monotonic()
        session_s = now - self._session_started_at if self._session_started_at is not None else 0
        self._total_label.configure(text=format_duration(self._previous_total_s + session_s))
        self._session_label.configure(text=f"{self._session_text()} · esta sesión: {format_duration(session_s)}")
        if self._stage_started_at is not None and self._stopped_at is None:
            self._stage_time_label.configure(
                text=f"En esta etapa: {format_duration(now - self._stage_started_at)}",
            )
        if reschedule and self._stopped_at is None:
            self._tick_job = self.app.after(1000, self._tick)
