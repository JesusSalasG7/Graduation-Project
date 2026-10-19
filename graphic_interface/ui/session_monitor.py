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
from ui.monitors import SLOT_TIMER, researcher_layout, tk_geometry

FONT_FAMILY = "Segoe UI"

# Nombre corto de cada etapa (ver session_wizard._update_session_monitor_stage).
STAGE_NAMES = {
    1: "Ver el juego",
    2: "El problema",
    3: "Tu prompt",
    4: "Resultado",
    5: "Razonamiento",
    6: "Solución en acción",
}


class SessionMonitorWindow:
    def __init__(
        self, app, colors: dict, scaled, participant_text: str,
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
        # Desglose por etapa del desafío actual: segundos ya cerrados de
        # cada etapa (sumando reintentos) y la etapa que está corriendo.
        self._challenge_key = None
        self._stage_totals: dict[int, float] = {}
        self._current_stage: Optional[int] = None

        window = ctk.CTkToplevel(app)
        window.title("Sesión en curso")
        slot = researcher_layout(app)[SLOT_TIMER]
        win_w = slot[2]
        window.geometry(tk_geometry(slot))
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
        self._stage_time_label.pack(anchor="w", fill="x", padx=16, pady=(0, 8))

        breakdown = ctk.CTkFrame(window, fg_color=colors["BG_CARD_ALT"], corner_radius=8)
        breakdown.pack(fill="x", padx=16, pady=(0, 12))
        breakdown.grid_columnconfigure(0, weight=1)
        row_font = ctk.CTkFont(family=FONT_FAMILY, size=scaled(11))
        time_font = ctk.CTkFont(family="monospace", size=scaled(11))
        self._stage_rows: dict[int, tuple[ctk.CTkLabel, ctk.CTkLabel]] = {}
        for stage, name in STAGE_NAMES.items():
            name_label = ctk.CTkLabel(breakdown, text=f"   {stage} · {name}", font=row_font, anchor="w", height=scaled(18))
            time_label = ctk.CTkLabel(breakdown, text="—", font=time_font, anchor="e", height=scaled(18))
            name_label.grid(row=stage - 1, column=0, sticky="w", padx=(10, 0), pady=(6 if stage == 1 else 0, 0))
            time_label.grid(row=stage - 1, column=1, sticky="e", padx=(0, 10), pady=(6 if stage == 1 else 0, 0))
            self._stage_rows[stage] = (name_label, time_label)
        bold = ctk.CTkFont(family=FONT_FAMILY, size=scaled(11), weight="bold")
        ctk.CTkLabel(breakdown, text="   Total del desafío", font=bold, anchor="w", height=scaled(20)).grid(
            row=len(STAGE_NAMES), column=0, sticky="w", padx=(10, 0), pady=(4, 6),
        )
        self._challenge_total_label = ctk.CTkLabel(
            breakdown, text="—", font=ctk.CTkFont(family="monospace", size=scaled(11), weight="bold"),
            anchor="e", height=scaled(20),
        )
        self._challenge_total_label.grid(row=len(STAGE_NAMES), column=1, sticky="e", padx=(0, 10), pady=(4, 6))

        self.window: Optional[ctk.CTkToplevel] = window
        self._tick()

    def _session_text(self) -> str:
        text = f"Sesión {self._session_number}"
        if self._session_number > 1:
            resumed = self._session_number - 1
            text += f" (retomada {resumed} {'vez' if resumed == 1 else 'veces'})"
        return text

    def set_position(
        self, challenge_text: str, stage_text: str, starts_session: bool = False,
        challenge_key=None, stage: Optional[int] = None,
    ):
        """Actualiza desafío/etapa y reinicia el tiempo de la etapa.
        `starts_session` arranca el cronómetro (solo la primera vez).
        `challenge_key`/`stage` alimentan el desglose por etapa: un
        `challenge_key` distinto al anterior lo reinicia (cambio de juego).
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
            self._close_current_stage(now)
            if challenge_key is not None and challenge_key != self._challenge_key:
                self._challenge_key = challenge_key
                self._stage_totals = {}
            self._current_stage = stage
            self._stage_started_at = now
        self._tick(reschedule=False)

    def _close_current_stage(self, now: float):
        """Pasa el tiempo de la etapa en curso a su total del desglose."""
        if self._current_stage is not None and self._stage_started_at is not None:
            self._stage_totals[self._current_stage] = (
                self._stage_totals.get(self._current_stage, 0) + now - self._stage_started_at
            )
        self._current_stage = None

    def _stage_seconds(self, stage: int, now: float) -> Optional[float]:
        seconds = self._stage_totals.get(stage)
        if stage == self._current_stage and self._stage_started_at is not None:
            seconds = (seconds or 0) + now - self._stage_started_at
        return seconds

    def _render_breakdown(self, now: float):
        total = 0.0
        for stage, (name_label, time_label) in self._stage_rows.items():
            seconds = self._stage_seconds(stage, now)
            running = stage == self._current_stage
            marker = "▶" if running else "  "
            name_label.configure(
                text=f"{marker} {stage} · {STAGE_NAMES[stage]}",
                text_color=self.c["ACCENT"] if running else ("white" if seconds is not None else self.c["TEXT_MUTED"]),
            )
            time_label.configure(
                text=format_duration(seconds) if seconds is not None else "—",
                text_color=self.c["ACCENT"] if running else ("white" if seconds is not None else self.c["TEXT_MUTED"]),
            )
            total += seconds or 0
        self._challenge_total_label.configure(text=format_duration(total) if self._stage_totals or self._current_stage else "—")

    def pause(self, reason: str):
        """Detiene el cronómetro ("Guardar progreso"/"Terminar sesión")."""
        if self.window is None or self._stopped_at is not None:
            return
        self._stopped_at = time.monotonic()
        self._tick(reschedule=False)
        self._close_current_stage(self._stopped_at)
        self._render_breakdown(self._stopped_at)
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
        self._render_breakdown(now)
        if reschedule and self._stopped_at is None:
            self._tick_job = self.app.after(1000, self._tick)
