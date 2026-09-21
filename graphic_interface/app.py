"""GUI principal: lanzador de juegos + gestion de participantes."""

import sys
import threading
import tkinter.messagebox as messagebox
from pathlib import Path
from tkinter import ttk
from typing import Optional

import customtkinter as ctk
import pandas as pd

from challenge_solver import GUIDED_SESSION_GAME_ORDER
from challenges import get_challenge
from difficulty import get_difficulty
from game_launcher import (
    PROJECT_ROOT,
    discover_games,
    open_in_vscode,
    play_game,
    repair_environment,
)
from isolated_prompt import claude_cli_available

# data/build_dataset.py vive fuera de graphic_interface (es parte del
# dataset consolidado de TODO el proyecto, no solo de esta app) -- se
# agrega al path para poder llamarlo desde la pestaña Sesion (ver
# App._generate_dataset) sin duplicar esa logica aca. Nombre distinto de
# DATA_DIR (mas abajo, graphic_interface/data/ -- participants.json, etc.)
# a proposito, para no pisarla.
DATASET_MODULE_DIR = PROJECT_ROOT / "data"
if str(DATASET_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(DATASET_MODULE_DIR))
from build_dataset import save_dataset  # noqa: E402
from participant_store import ParticipantStore, participant_file_stub, participant_label
from personal_records import save_personal_record
from session_wizard import SessionWizard
from stage_capture import GUIDED_SESSION_STAGE_ORDER, challenge_dir_readonly, summarize_stage
from statement_view import render_statement

# tkinterdnd2 habilita arrastrar-y-soltar el CSV de frecuencia cardiaca del
# reloj (ver heart_rate_import.py) -- es una dependencia opcional: si no
# esta instalada (o el .venv todavia no se reparo, ver repair_environment),
# la app sigue andando normal, solo sin esa pantalla pudiendo recibir un
# arrastre real (queda el boton "Seleccionar archivo").
try:
    from tkinterdnd2 import TkinterDnD
    _DND_MIXIN = (TkinterDnD.DnDWrapper,)
except ImportError:
    TkinterDnD = None
    _DND_MIXIN = ()

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_FILE = DATA_DIR / "participants.json"

EXPERIENCE_LEVELS = [
    "Avanzado",
    "Intermedio",
    "Principiante",
]

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Paleta de la app (tema oscuro fijo)
BG_APP = "#15171d"
BG_SIDEBAR = "#101217"
BG_CARD = "#1e212a"
BG_CARD_ALT = "#252834"
BORDER = "#2c303c"
TEXT_MUTED = "#9ea3ba"  # mas claro que el original (#8b8fa3): ese no llegaba a
                        # contraste 4.5:1 (WCAG AA) sobre BG_CARD_ALT

ACCENT = "#5865f2"
ACCENT_HOVER = "#4752c4"
NAV_HOVER = "#1b1e27"

SUCCESS = "#2fb344"
SUCCESS_HOVER = "#23902f"
DANGER = "#e5484d"
DANGER_HOVER = "#c93a3f"
WARNING = "#f2994a"
WARNING_HOVER = "#d97f34"

FONT_FAMILY = "Segoe UI"

# Toda la tipografia del panel principal se agranda un 50% (pedido explicito).
FONT_SCALE = 1.5


def scaled(size: int) -> int:
    return round(size * FONT_SCALE)


# Los anchos de wrapeo y las dimensiones de ventanas/modales crecen mas
# suave que la letra (60% del aumento) -- si crecieran al mismo ritmo que
# la fuente, ocuparian mucha mas pantalla de la necesaria.
WRAP_SCALE = 1 + (FONT_SCALE - 1) * 0.6


def wrap(px: int) -> int:
    return round(px * WRAP_SCALE)


def _enable_linux_wheel_scroll(root: ctk.CTk) -> None:
    """CTkScrollableFrame solo escucha <MouseWheel>, que en la mayoria de
    los Linux/X11 nunca se dispara -- la rueda del mouse llega como
    <Button-4> (arriba) / <Button-5> (abajo). Sin esto, el scroll con la
    rueda no funciona en NINGUNA CTkScrollableFrame de la app (lista de
    juegos, enunciado del desafio, preguntas de la sesion guiada, etc.).

    Se registra una sola vez, a nivel de la ventana raiz: bind_all() es
    global al interprete de Tcl, asi que cubre tambien los CTkToplevel
    (modales) que se abran despues, sin tener que repetir esto en cada
    lugar donde se crea una CTkScrollableFrame.
    """

    def _scrollable_ancestor(widget):
        while widget is not None:
            if isinstance(widget, ctk.CTkScrollableFrame):
                return widget
            widget = getattr(widget, "master", None)
        return None

    def _on_wheel(event, direction: int):
        target = _scrollable_ancestor(event.widget)
        if target is None:
            return
        # Igual que el _mouse_wheel_all interno de customtkinter: si
        # yview() ya es (0.0, 1.0), todo el contenido entra en la vista y
        # no hay nada que desplazar -- moverlo igual saca el canvas de
        # sus limites visibles (contenido "flotando" fuera del marco).
        if target._parent_canvas.yview() != (0.0, 1.0):
            target._parent_canvas.yview_scroll(direction, "units")

    root.bind_all("<Button-4>", lambda e: _on_wheel(e, -1))
    root.bind_all("<Button-5>", lambda e: _on_wheel(e, 1))


class App(ctk.CTk, *_DND_MIXIN):
    def __init__(self):
        super().__init__()
        self.title("Panel de Experimento")
        self.geometry(f"{wrap(1080)}x{wrap(680)}")
        self.minsize(wrap(920), wrap(580))
        self.configure(fg_color=BG_APP)
        _enable_linux_wheel_scroll(self)

        # Registra el soporte de arrastrar-y-soltar en esta ventana raiz
        # (ver heart_rate_import.register_drop_target) -- sin esto ningun
        # widget de la app puede recibir un drop, aunque tkinterdnd2 este
        # instalado. Si falla (Tcl del sistema sin el paquete tkdnd, etc.)
        # la app sigue funcionando, solo sin arrastrar-y-soltar real.
        self.dnd_available = False
        if TkinterDnD is not None:
            try:
                self.TkdndVersion = TkinterDnD._require(self)
                self.dnd_available = True
            except Exception:
                pass
        # La app arranca ya maximizada (pedido explicito) en vez del tamano
        # fijo de arriba, que queda solo como base/minsize.
        self.after(0, self._maximize)

        self.store = ParticipantStore(DATA_FILE)
        self.sort_games_by_difficulty = False

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._nav_buttons: dict[str, ctk.CTkButton] = {}
        self._build_sidebar()

        self.content = ctk.CTkFrame(self, fg_color=BG_APP)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        self.tab_games = ctk.CTkFrame(self.content, fg_color=BG_APP)
        self.tab_participants = ctk.CTkFrame(self.content, fg_color=BG_APP)
        self.tab_session = ctk.CTkFrame(self.content, fg_color=BG_APP)
        for frame in (
            self.tab_games, self.tab_participants, self.tab_session,
        ):
            frame.grid(row=0, column=0, sticky="nsew")

        self._build_games_tab()
        self._build_participants_tab()
        self._build_session_tab()
        self._select_nav("games")

        # Sesion guiada: un frame que ocupa TODA la ventana (sidebar +
        # contenido) por encima de todo lo demas, oculto hasta que se entra
        # explicitamente via enter_session_wizard().
        self.session_wizard_frame = ctk.CTkFrame(self, fg_color=BG_APP)
        self.session_wizard_frame.grid(row=0, column=0, columnspan=2, sticky="nsew")
        self.session_wizard_frame.lower()
        self.session_wizard = SessionWizard(
            self.session_wizard_frame, self,
            {
                "ACCENT": ACCENT, "ACCENT_HOVER": ACCENT_HOVER,
                "BG_CARD": BG_CARD, "BG_CARD_ALT": BG_CARD_ALT,
                "BORDER": BORDER, "TEXT_MUTED": TEXT_MUTED, "WARNING": WARNING,
            },
        )

    def enter_session_wizard(self):
        if self.store.get_active() is None:
            messagebox.showinfo(
                "Sin participante activo",
                "Selecciona un participante activo en la pestaña Participantes primero.",
            )
            return
        if not claude_cli_available():
            continue_anyway = messagebox.askyesno(
                "No se detectó Claude Code",
                "No se encontró el CLI 'claude' instalado en este equipo.\n\n"
                "Las Etapas 3, 4 y 5 de la sesión guiada dependen de él para "
                "generar la respuesta de la IA y los cuestionarios -- sin "
                "Claude Code, esas etapas van a mostrar un error en vez de "
                "funcionar. El resto de la sesión (juegos, sensores, "
                "Etapa 2) funciona igual.\n\n"
                "¿Continuar de todas formas?",
            )
            if not continue_anyway:
                return
        self._ask_session_devices(self._begin_session_wizard)

    def _begin_session_wizard(self, enabled_devices):
        if enabled_devices is None:
            return  # se cancelo el modal de dispositivos -- no se entra a la sesion
        # La app entera arranca maximizada (ver __init__); esto solo
        # cubre el caso de que el usuario la haya desmaximizado a mano.
        self._maximize()
        # Pantalla completa de verdad (sin barra de titulo ni barra de
        # tareas) durante toda la sesion guiada -- pedido explicito, para
        # que el participante solo tenga a la vista el propio asistente y
        # no se distraiga con el resto del escritorio.
        self._set_fullscreen(True)
        self.session_wizard_frame.tkraise()
        self.session_wizard.start(enabled_devices)

    def _ask_session_devices(self, on_done):
        """Modal previo a entrar a la sesion guiada: que dispositivos se
        van a usar esta vez -- todos tildados por defecto. Si se destilda
        alguno, la sesion guiada sigue funcionando igual, solo sin pedir
        ni procesar los datos de ese dispositivo (ver SessionWizard.
        _enabled_devices / _show_next_setup_screen). `on_done` recibe el
        set de dispositivos elegidos, o None si se cancelo."""
        modal = ctk.CTkToplevel(self)
        modal.title("Dispositivos de esta sesión")
        modal.geometry(f"{wrap(440)}x{wrap(360)}")
        modal.configure(fg_color=BG_CARD)
        modal.transient(self)
        modal.resizable(False, False)
        modal.wait_visibility()
        modal.attributes("-topmost", True)
        modal.lift()
        modal.focus_force()

        def finish(devices):
            try:
                modal.grab_release()
            except Exception:
                pass
            modal.destroy()
            on_done(devices)

        modal.protocol("WM_DELETE_WINDOW", lambda: finish(None))
        modal.grab_set()

        ctk.CTkLabel(
            modal, text="⚙️  ¿Qué dispositivos vas a usar en esta sesión?",
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(15), weight="bold"),
            wraplength=wrap(380), justify="left",
        ).pack(pady=(24, 6), padx=24)
        ctk.CTkLabel(
            modal,
            text="Destilda los que no vayas a usar -- la sesión va a seguir "
                 "funcionando igual, solo sin pedir ni procesar los datos de "
                 "esos dispositivos.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(11)), text_color=TEXT_MUTED,
            wraplength=wrap(380), justify="left",
        ).pack(pady=(0, 18), padx=24)

        device_vars = {
            "heart_rate": ctk.BooleanVar(value=True),
            "neurosky": ctk.BooleanVar(value=True),
            "camera": ctk.BooleanVar(value=True),
        }
        device_labels = {
            "heart_rate": "⌚  Reloj (frecuencia cardíaca)",
            "neurosky": "🧠  NeuroSky",
            "camera": "📷  Cámara (Emotion + Eye Tracker)",
        }
        for device in ("heart_rate", "neurosky", "camera"):
            ctk.CTkCheckBox(
                modal, text=device_labels[device], variable=device_vars[device],
                font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(13)),
                fg_color=ACCENT, hover_color=ACCENT_HOVER,
            ).pack(anchor="w", padx=44, pady=7)

        buttons_row = ctk.CTkFrame(modal, fg_color="transparent")
        buttons_row.pack(pady=(22, 0))
        ctk.CTkButton(
            buttons_row, text="Cancelar", width=scaled(110), height=scaled(34), corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12)),
            fg_color="transparent", hover_color=NAV_HOVER, border_width=1, border_color=BORDER,
            command=lambda: finish(None),
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            buttons_row, text="Continuar  ▶", width=scaled(150), height=scaled(34), corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12), weight="bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=lambda: finish({device for device, var in device_vars.items() if var.get()}),
        ).pack(side="left")

    def exit_session_wizard(self):
        self._set_fullscreen(False)
        self.session_wizard_frame.lower()
        self._select_nav("session")
        # No se restaura ningun tamano "chico": la ventana siempre vive
        # maximizada, asi que simplemente se deja como esta (evita el bug
        # de que forzar state("normal") + geometry la dejaba minimizada).
        self._maximize()

    def _set_fullscreen(self, value: bool):
        try:
            self.attributes("-fullscreen", value)
        except Exception:
            pass

    def _maximize(self):
        try:
            self.state("zoomed")
            return
        except Exception:
            pass
        try:
            self.attributes("-zoomed", True)
            return
        except Exception:
            pass
        self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")

    # ---------------- Sidebar / navegacion ----------------
    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, width=scaled(230), corner_radius=0, fg_color=BG_SIDEBAR)
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_propagate(False)

        brand = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand.pack(fill="x", padx=20, pady=(26, 30))
        ctk.CTkLabel(
            brand, text="🎮 Vibe Coding", font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(19), weight="bold")
        ).pack(anchor="w")
        ctk.CTkLabel(
            brand, text="Panel de experimento", font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12)),
            text_color=TEXT_MUTED,
        ).pack(anchor="w", pady=(2, 0))

        nav = ctk.CTkFrame(sidebar, fg_color="transparent")
        nav.pack(fill="x", padx=14)

        self._nav_buttons["games"] = self._nav_button(nav, "🕹️  Juegos", "games")
        self._nav_buttons["participants"] = self._nav_button(nav, "🧑‍🤝‍🧑  Participantes", "participants")
        self._nav_buttons["session"] = self._nav_button(nav, "⏱️  Sesión", "session")

        footer = ctk.CTkFrame(sidebar, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=20, pady=18)

        ctk.CTkLabel(
            footer, text=f"Proyecto: {PROJECT_ROOT.name}", font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(10)),
            text_color=TEXT_MUTED, wraplength=wrap(190), justify="left",
        ).pack(anchor="w")

    def _nav_button(self, parent, text, key):
        btn = ctk.CTkButton(
            parent,
            text=text,
            anchor="w",
            corner_radius=8,
            height=scaled(42),
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(13)),
            fg_color="transparent",
            hover_color=NAV_HOVER,
            text_color="#c9cdd9",
            command=lambda: self._select_nav(key),
        )
        btn.pack(fill="x", pady=3)
        return btn

    def _select_nav(self, key):
        frames = {
            "games": self.tab_games,
            "participants": self.tab_participants,
            "session": self.tab_session,
        }
        for name, btn in self._nav_buttons.items():
            active = name == key
            btn.configure(
                fg_color=ACCENT if active else "transparent",
                text_color="white" if active else "#c9cdd9",
                hover_color=ACCENT_HOVER if active else NAV_HOVER,
            )
        frames[key].tkraise()
        if key == "session":
            # Recalcula la matriz de "Datos guardados" al entrar a la
            # pestaña -- lee de disco, asi que refleja lo que se haya
            # exportado desde la ultima vez que se miro esta vista.
            self._refresh_session_data_matrix()

    # ---------------- Juegos ----------------
    def _build_games_tab(self):
        header = ctk.CTkFrame(self.tab_games, fg_color="transparent")
        header.pack(fill="x", padx=26, pady=(24, 6))

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            title_box, text="Juegos", font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(22), weight="bold")
        ).pack(anchor="w")
        self.active_label = ctk.CTkLabel(
            title_box, text=self._active_label_text(), font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12)),
            text_color=TEXT_MUTED,
        )
        self.active_label.pack(anchor="w", pady=(2, 0))

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right")

        self.repair_button = ctk.CTkButton(
            actions, text="🛠️  Reparar entorno", width=scaled(160), height=scaled(34), corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12), weight="bold"),
            fg_color=WARNING, hover_color=WARNING_HOVER, text_color="#1a1a1a",
            command=self._repair_environment,
        )
        self.repair_button.pack(side="left", padx=(0, 8))

        self.difficulty_button = ctk.CTkButton(
            actions, text="📊  Ver juegos en dificultad", width=scaled(210), height=scaled(34), corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12)),
            fg_color=BG_CARD_ALT, hover_color=BORDER, text_color="white",
            command=self._toggle_difficulty_view,
        )
        self.difficulty_button.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            actions, text="🔄  Actualizar", width=scaled(130), height=scaled(34), corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12)),
            fg_color=BG_CARD_ALT, hover_color=BORDER, text_color="white",
            command=self._refresh_games,
        ).pack(side="left")

        self.games_scroll = ctk.CTkScrollableFrame(self.tab_games, fg_color="transparent")
        self.games_scroll.pack(fill="both", expand=True, padx=20, pady=10)

        self._refresh_games()

    def _toggle_difficulty_view(self):
        self.sort_games_by_difficulty = not self.sort_games_by_difficulty
        if self.sort_games_by_difficulty:
            self.difficulty_button.configure(
                text="🔤  Ver en orden normal", fg_color=ACCENT, hover_color=ACCENT_HOVER,
            )
        else:
            self.difficulty_button.configure(
                text="📊  Ver juegos en dificultad", fg_color=BG_CARD_ALT, hover_color=BORDER,
            )
        self._refresh_games()

    @staticmethod
    def _difficulty_colors(tier: str) -> tuple[str, str]:
        if tier == "Fácil":
            return "#1c3a26", "#4ade80"
        if tier in ("Media", "Media-alta"):
            return "#332a1c", "#c9a15a"
        return "#3a1c1e", "#f87171"

    def _refresh_games(self):
        for child in self.games_scroll.winfo_children():
            child.destroy()

        games = discover_games()
        if not games:
            ctk.CTkLabel(
                self.games_scroll, text="No se encontraron carpetas Game-*.", text_color=TEXT_MUTED
            ).pack(pady=20)
            return

        if self.sort_games_by_difficulty:
            games = sorted(
                games,
                key=lambda g: get_difficulty(g.name).rank if get_difficulty(g.name) else 99,
            )

        for game in games:
            card = ctk.CTkFrame(self.games_scroll, fg_color=BG_CARD, corner_radius=12)
            card.pack(fill="x", pady=6, padx=4)
            card.grid_columnconfigure(0, weight=1)

            info = ctk.CTkFrame(card, fg_color="transparent")
            info.grid(row=0, column=0, sticky="w", padx=18, pady=14)

            title_row = ctk.CTkFrame(info, fg_color="transparent")
            title_row.pack(anchor="w")
            if self.sort_games_by_difficulty:
                main_text, sub_text = game.display_name, game.name
            else:
                main_text, sub_text = game.name, game.display_name
            ctk.CTkLabel(
                title_row, text=f"🎲  {main_text}", font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(15), weight="bold")
            ).pack(side="left")
            if sub_text and sub_text != main_text:
                ctk.CTkLabel(
                    title_row, text=f"   ·   {sub_text}",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(13)), text_color=TEXT_MUTED,
                ).pack(side="left")

            pills_row = ctk.CTkFrame(info, fg_color="transparent")
            pills_row.pack(anchor="w", pady=(6, 0))

            if game.is_playable:
                pill_text, pill_bg, pill_fg = "● Listo para jugar", "#1c3a26", "#4ade80"
            else:
                pill_text, pill_bg, pill_fg = "● Sin main.py", "#332a1c", "#c9a15a"
            ctk.CTkLabel(
                pills_row, text=pill_text, font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(11), weight="bold"),
                fg_color=pill_bg, text_color=pill_fg, corner_radius=10, padx=10, pady=2,
            ).pack(side="left")

            difficulty = get_difficulty(game.name)
            if difficulty:
                diff_bg, diff_fg = self._difficulty_colors(difficulty.tier)
                ctk.CTkLabel(
                    pills_row, text=f"🎯 {difficulty.rank}/7 · {difficulty.tier}",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(11), weight="bold"),
                    fg_color=diff_bg, text_color=diff_fg, corner_radius=10, padx=10, pady=2,
                ).pack(side="left", padx=(8, 0))

            buttons = ctk.CTkFrame(card, fg_color="transparent")
            buttons.grid(row=0, column=1, sticky="e", padx=18, pady=14)

            ctk.CTkButton(
                buttons, text="📝  VS Code", width=scaled(130), height=scaled(34), corner_radius=8,
                font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12)),
                fg_color=BG_CARD_ALT, hover_color=BORDER, text_color="white",
                command=lambda g=game: self._open_vscode(g),
            ).pack(side="left", padx=(0, 8))

            statement_btn = ctk.CTkButton(
                buttons, text="📄  Ver enunciado del desafío", width=scaled(210), height=scaled(34), corner_radius=8,
                font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12)),
                fg_color=BG_CARD_ALT, hover_color=BORDER, text_color="white",
                command=lambda g=game: self._show_statement_modal(g),
            )
            statement_btn.pack(side="left", padx=(0, 8))
            if get_challenge(game.name) is None:
                statement_btn.configure(state="disabled", text_color=TEXT_MUTED)

            play_btn = ctk.CTkButton(
                buttons, text="▶  Jugar", width=scaled(110), height=scaled(34), corner_radius=8,
                font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12), weight="bold"),
                fg_color=SUCCESS, hover_color=SUCCESS_HOVER,
                command=lambda g=game: self._play(g),
            )
            play_btn.pack(side="left")
            if not game.is_playable:
                play_btn.configure(state="disabled", fg_color=BG_CARD_ALT, text_color=TEXT_MUTED)

    def _show_statement_modal(self, game):
        challenge = get_challenge(game.name)
        if challenge is None:
            messagebox.showinfo(
                "Sin desafío definido",
                f"{game.name} no tiene un desafío configurado en la sesión guiada.",
            )
            return

        modal = ctk.CTkToplevel(self)
        modal.title(f"Enunciado — {challenge.title}")
        modal.geometry(f"{wrap(760)}x{wrap(680)}")
        modal.configure(fg_color=BG_APP)
        modal.transient(self)
        modal.wait_visibility()
        modal.grab_set()

        header = ctk.CTkFrame(modal, fg_color="transparent")
        header.pack(fill="x", padx=26, pady=(20, 6))
        ctk.CTkLabel(
            header, text=challenge.title,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(18), weight="bold"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text="Esto es exactamente lo que va a ver el participante en la Etapa 1 de la sesión guiada.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12)), text_color=TEXT_MUTED,
        ).pack(anchor="w", pady=(2, 0))

        scroll = ctk.CTkScrollableFrame(modal, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=26, pady=(10, 10))

        render_statement(
            scroll, game, challenge,
            {
                "ACCENT": ACCENT, "ACCENT_HOVER": ACCENT_HOVER,
                "BG_CARD": BG_CARD, "BG_CARD_ALT": BG_CARD_ALT,
                "BORDER": BORDER, "TEXT_MUTED": TEXT_MUTED, "WARNING": WARNING,
            },
            wraplength=wrap(680),
            font_scale=FONT_SCALE,
        )

        ctk.CTkButton(
            modal, text="Cerrar", height=scaled(36), width=scaled(120), corner_radius=8,
            fg_color=BG_CARD_ALT, hover_color=BORDER, command=modal.destroy,
        ).pack(pady=(0, 18))

    def _open_vscode(self, game):
        try:
            open_in_vscode(game)
        except FileNotFoundError:
            messagebox.showerror(
                "VS Code no encontrado",
                "No se encontró el comando 'code' en el PATH. Instala el CLI de VS Code e intenta de nuevo.",
            )
            return

    def _on_close(self):
        # Si la app se cierra de golpe con una sesion guiada de Neurosky
        # todavia activa, la da por incompleta: para el proceso, borra los
        # datos capturados y trata de desvincular el dispositivo antes de
        # que la ventana desaparezca (ver SessionWizard.cleanup_incomplete_session).
        self.session_wizard.cleanup_incomplete_session()
        self.destroy()

    def _repair_environment(self):
        self.repair_button.configure(state="disabled", text="Reparando...")

        log_win = ctk.CTkToplevel(self)
        log_win.title("Reparando entorno (.venv)")
        log_win.geometry(f"{wrap(620)}x{wrap(400)}")
        log_win.configure(fg_color=BG_APP)
        log_win.transient(self)

        ctk.CTkLabel(
            log_win, text="🛠️  Reinstalando dependencias en el .venv unificado",
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(13), weight="bold"),
        ).pack(anchor="w", padx=14, pady=(14, 6))

        textbox = ctk.CTkTextbox(
            log_win, wrap="word", font=ctk.CTkFont(family="monospace", size=scaled(11)),
            fg_color=BG_CARD, corner_radius=10,
        )
        textbox.pack(fill="both", expand=True, padx=14, pady=(0, 8))

        close_btn = ctk.CTkButton(
            log_win, text="Cerrar", state="disabled", width=scaled(120), corner_radius=8,
            fg_color=BG_CARD_ALT, hover_color=BORDER, command=log_win.destroy,
        )
        close_btn.pack(pady=(0, 14))

        def append_line(line: str):
            def _do():
                textbox.insert("end", line + "\n")
                textbox.see("end")
            self.after(0, _do)

        def worker():
            ok, _log = repair_environment(on_output=append_line)

            def finish():
                self.repair_button.configure(state="normal", text="🛠️  Reparar entorno")
                close_btn.configure(state="normal")
                if ok:
                    append_line("\n>> Entorno reparado correctamente.")
                    messagebox.showinfo(
                        "Entorno reparado",
                        "Las dependencias de todos los juegos y de la GUI se reinstalaron en el .venv.",
                    )
                else:
                    append_line("\n>> Ocurrió un error reparando el entorno. Revisa el log.")
                    messagebox.showerror(
                        "Error al reparar",
                        "No se pudo reinstalar alguna dependencia. Revisa la ventana de log para mas detalles.",
                    )
                self._refresh_games()

            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def _play(self, game):
        active = self.store.get_active()
        if active is None:
            proceed = messagebox.askyesno(
                "Sin participante activo",
                "No hay un participante activo seleccionado. ¿Deseas iniciar el juego de todas formas?",
            )
            if not proceed:
                return
        try:
            play_game(game)
        except FileNotFoundError as exc:
            messagebox.showerror("No se pudo lanzar el juego", str(exc))

    # ---------------- Participantes ----------------
    def _active_label_text(self) -> str:
        active = self.store.get_active()
        if active:
            return f"👤 Participante activo: {participant_label(active)}"
        return "👤 Participante activo: ninguno"

    def _participant_count_text(self) -> str:
        count = len(self.store.list_participants())
        label = "participante registrado" if count == 1 else "participantes registrados"
        return f"👥 {count} {label}"

    def _build_participants_tab(self):
        wrapper = ctk.CTkFrame(self.tab_participants, fg_color="transparent")
        wrapper.pack(fill="both", expand=True, padx=26, pady=(24, 20))

        title_row = ctk.CTkFrame(wrapper, fg_color="transparent")
        title_row.pack(fill="x")
        ctk.CTkLabel(
            title_row, text="Participantes", font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(22), weight="bold")
        ).pack(side="left")
        self.participant_count_label = ctk.CTkLabel(
            title_row, text=self._participant_count_text(),
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12), weight="bold"),
            fg_color=BG_CARD_ALT, corner_radius=10, text_color="#c9cdd9", padx=12, pady=4,
        )
        self.participant_count_label.pack(side="right")
        ctk.CTkLabel(
            wrapper, text="Registra sujetos de prueba. Haz clic en una fila de la tabla para marcarlo como activo.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12)), text_color=TEXT_MUTED,
        ).pack(anchor="w", pady=(2, 14))

        container = ctk.CTkFrame(wrapper, fg_color="transparent")
        container.pack(fill="both", expand=True)
        container.grid_columnconfigure(1, weight=1)
        container.grid_rowconfigure(0, weight=1)

        form = ctk.CTkFrame(container, fg_color=BG_CARD, corner_radius=12)
        form.grid(row=0, column=0, sticky="nsw", padx=(0, 14))

        ctk.CTkLabel(
            form, text="➕  Nuevo participante", font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(15), weight="bold")
        ).pack(anchor="w", padx=18, pady=(18, 8))
        ctk.CTkLabel(
            form,
            text="Dentro de la app cada participante es anónimo\n(Participante 1, Participante 2, ...). El nombre y\napellido que pidas al agregarlo se guardan aparte,\nen tu Escritorio, no en los datos de la sesión.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(11)), text_color=TEXT_MUTED,
            justify="left",
        ).pack(anchor="w", padx=18, pady=(0, 16))

        ctk.CTkButton(
            form, text="💾  Agregar participante", height=scaled(36), corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12), weight="bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._open_add_participant_modal,
        ).pack(fill="x", padx=18, pady=(8, 8))
        ctk.CTkButton(
            form, text="🗑️  Eliminar seleccionado", height=scaled(36), corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12)),
            fg_color="transparent", hover_color=DANGER, border_width=1, border_color=DANGER,
            text_color=DANGER,
            command=self._delete_selected,
        ).pack(fill="x", padx=18, pady=(0, 18))

        table_frame = ctk.CTkFrame(container, fg_color=BG_CARD, corner_radius=12)
        table_frame.grid(row=0, column=1, sticky="nsew")
        table_frame.grid_rowconfigure(1, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        self.participants_active_label = ctk.CTkLabel(
            table_frame, text=self._active_label_text(), font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12), weight="bold"),
            fg_color=BG_CARD_ALT, corner_radius=8, anchor="w",
        )
        self.participants_active_label.grid(row=0, column=0, columnspan=2, sticky="ew", padx=16, pady=(16, 10), ipady=6)

        self._style_treeview()

        columns = ("participante", "nivel", "fecha")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        for col, label, width in (
            ("participante", "Participante", scaled(160)),
            ("nivel", "Nivel de experiencia", scaled(220)),
            ("fecha", "Registrado", scaled(180)),
        ):
            self.tree.heading(col, text=label, anchor="center")
            self.tree.column(col, width=width, anchor="center")
        self.tree.grid(row=1, column=0, sticky="nsew", padx=(16, 0), pady=(0, 16))
        self.tree.bind("<<TreeviewSelect>>", self._on_participant_selected)

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=1, column=1, sticky="ns", padx=(0, 16), pady=(0, 16))

        self._refresh_participants()

    def _style_treeview(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background=BG_CARD_ALT,
            foreground="#e6e8f0",
            fieldbackground=BG_CARD_ALT,
            bordercolor=BG_CARD,
            borderwidth=0,
            rowheight=scaled(30),
            font=(FONT_FAMILY, scaled(11)),
        )
        style.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", "white")])
        style.configure(
            "Treeview.Heading",
            background=BG_CARD,
            foreground=TEXT_MUTED,
            borderwidth=0,
            relief="flat",
            font=(FONT_FAMILY, scaled(11), "bold"),
        )
        style.map("Treeview.Heading", background=[("active", BG_CARD)])
        style.configure("Vertical.TScrollbar", background=BG_CARD_ALT, troughcolor=BG_CARD, bordercolor=BG_CARD)

    def _refresh_participants(self):
        self.tree.delete(*self.tree.get_children())
        for p in self.store.list_participants():
            nivel = p.get("attributes", {}).get("nivel_experiencia", "—")
            self.tree.insert("", "end", iid=p["id"], values=(participant_label(p), nivel, p["created_at"]))
        active = self.store.get_active()
        if active is not None:
            self.tree.selection_set(active["id"])
        self.active_label.configure(text=self._active_label_text())
        self.participants_active_label.configure(text=self._active_label_text())
        self.participant_count_label.configure(text=self._participant_count_text())
        count = len(self.store.list_participants())
        self._nav_buttons["participants"].configure(text=f"🧑‍🤝‍🧑  Participantes ({count})")

    def _open_add_participant_modal(self):
        modal = ctk.CTkToplevel(self)
        modal.title("Nuevo participante")
        modal.geometry(f"{wrap(400)}x{wrap(420)}")
        modal.configure(fg_color=BG_APP)
        modal.transient(self)
        modal.resizable(False, False)
        # grab_set() debe esperar a que la ventana ya este dibujada en pantalla,
        # si no lanza "grab failed: window not viewable".
        modal.wait_visibility()
        modal.grab_set()

        ctk.CTkLabel(
            modal, text="➕  Nuevo participante",
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(18), weight="bold"),
        ).pack(pady=(26, 8))
        ctk.CTkLabel(
            modal,
            text=(
                "El nombre y apellido son datos personales: se guardan\n"
                "solo en tu Escritorio (carpeta \"Participantes\"), nunca\n"
                "en los datos anónimos de la sesión (emociones, BPM, etc.),\n"
                "que dentro de la app siguen identificando a esta persona\n"
                "únicamente como su número de participante."
            ),
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(11)), text_color=TEXT_MUTED, justify="center",
        ).pack(padx=24, pady=(0, 16))

        entry_nombre = ctk.CTkEntry(
            modal, width=scaled(260), height=scaled(34), corner_radius=8, fg_color=BG_CARD_ALT, border_width=0,
            placeholder_text="Nombre",
        )
        entry_nombre.pack(pady=(0, 10))
        entry_apellido = ctk.CTkEntry(
            modal, width=scaled(260), height=scaled(34), corner_radius=8, fg_color=BG_CARD_ALT, border_width=0,
            placeholder_text="Apellido",
        )
        entry_apellido.pack(pady=(0, 14))
        entry_nombre.focus_set()

        ctk.CTkLabel(
            modal, text="Nivel de experiencia", font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12)),
            text_color=TEXT_MUTED,
        ).pack(anchor="center")
        experience_menu = ctk.CTkOptionMenu(
            modal, width=scaled(260), height=scaled(34), corner_radius=8,
            values=EXPERIENCE_LEVELS,
            fg_color=BG_CARD_ALT, button_color=BORDER, button_hover_color=ACCENT,
        )
        experience_menu.pack(pady=(4, 18))

        def on_accept():
            nombre = entry_nombre.get().strip()
            apellido = entry_apellido.get().strip()
            experience_level = experience_menu.get()
            if not nombre or not apellido:
                messagebox.showwarning(
                    "Datos incompletos", "Nombre y apellido son obligatorios.", parent=modal,
                )
                return

            participant = self.store.add_participant(nivel_experiencia=experience_level)
            try:
                record_path = save_personal_record(participant["number"], nombre, apellido)
            except OSError as exc:
                messagebox.showerror(
                    "No se pudo guardar el registro personal",
                    f"Se creó {participant_label(participant)} en la app, pero no se pudo "
                    f"guardar el nombre en el Escritorio:\n{exc}",
                    parent=modal,
                )
            else:
                messagebox.showinfo(
                    "Participante agregado",
                    f"Se creó {participant_label(participant)}.\n\n"
                    f"El nombre se guardó en:\n{record_path}",
                    parent=modal,
                )

            self._refresh_participants()
            modal.destroy()

        buttons_row = ctk.CTkFrame(modal, fg_color="transparent")
        buttons_row.pack()
        ctk.CTkButton(
            buttons_row, text="Cancelar", width=scaled(110), height=scaled(36), corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12)),
            fg_color="transparent", hover_color=BORDER, border_width=1, border_color=BORDER,
            command=modal.destroy,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            buttons_row, text="Guardar", width=scaled(110), height=scaled(36), corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12), weight="bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=on_accept,
        ).pack(side="left")

    def _selected_id(self):
        selection = self.tree.selection()
        return selection[0] if selection else None

    def _on_participant_selected(self, event=None):
        pid = self._selected_id()
        if not pid:
            return
        active = self.store.get_active()
        if active is not None and active["id"] == pid:
            return
        self.store.set_active(pid)
        self._refresh_participants()
        self._refresh_session_tab()
        self._refresh_session_data_matrix()

    def _delete_selected(self):
        pid = self._selected_id()
        if not pid:
            messagebox.showinfo("Sin selección", "Selecciona un participante de la tabla primero.")
            return
        if messagebox.askyesno("Confirmar", "¿Eliminar este participante?"):
            self.store.delete_participant(pid)
            self._refresh_participants()

    # ---------------- Sesion ----------------
    def _build_session_tab(self):
        # Scrollable: con la tarjeta de "Dataset consolidado" agregada abajo
        # de "Datos guardados" ya no entran ambas expandiendose en la altura
        # fija de la pestaña -- con esto la pestaña entera se puede
        # desplazar en vez de aplastar una tarjeta contra la otra.
        wrapper = ctk.CTkScrollableFrame(self.tab_session, fg_color="transparent")
        wrapper.pack(fill="both", expand=True, padx=26, pady=(24, 20))

        ctk.CTkLabel(
            wrapper, text="Sesión", font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(22), weight="bold")
        ).pack(anchor="w")
        ctk.CTkLabel(
            wrapper,
            text="Comienza la sesión guiada de desafíos para el participante activo.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12)), text_color=TEXT_MUTED,
        ).pack(anchor="w", pady=(2, 14))

        guided_card = ctk.CTkFrame(wrapper, fg_color=BG_CARD, corner_radius=12)
        guided_card.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(
            guided_card, text="🚀  Sesión guiada de desafíos",
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(13), weight="bold"),
        ).pack(anchor="w", padx=18, pady=(16, 4))
        self.guided_session_button = ctk.CTkButton(
            guided_card, text=self._guided_session_button_text(), height=scaled(36), width=scaled(280),
            corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12), weight="bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self.enter_session_wizard,
        )
        self.guided_session_button.pack(anchor="w", padx=18, pady=(4, 18))

        # ---------------- Datos guardados (leidos de disco, no de memoria) ----------------
        # Matriz de lo que ya se exporto para el participante activo, leyendo
        # directo de Sesiones_participantes/<Nombre_Apellido_N>/Desafio_N/
        # Etapa_N/ (ver stage_capture.py) -- las Etapas 1 y 6 no capturan
        # datos (ver GUIDED_SESSION_STAGE_ORDER), asi que no se listan.
        data_card = ctk.CTkFrame(wrapper, fg_color=BG_CARD, corner_radius=12)
        data_card.pack(fill="x", pady=(0, 14))

        ctk.CTkLabel(
            data_card, text="📊  Datos guardados",
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(13), weight="bold"),
        ).pack(anchor="w", padx=18, pady=(16, 4))

        selector_row = ctk.CTkFrame(data_card, fg_color="transparent")
        selector_row.pack(fill="x", padx=18, pady=(0, 10))
        ctk.CTkLabel(
            selector_row, text="Desafío", font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12)),
            text_color=TEXT_MUTED,
        ).pack(side="left", padx=(0, 8))
        self.session_data_challenge_menu = ctk.CTkOptionMenu(
            selector_row, values=[str(n) for n in range(1, len(GUIDED_SESSION_GAME_ORDER) + 1)],
            width=scaled(80), fg_color=BG_CARD_ALT, button_color=BORDER, button_hover_color=ACCENT,
            command=lambda _value: self._refresh_session_data_matrix(),
        )
        self.session_data_challenge_menu.pack(side="left")

        tree_frame = ctk.CTkFrame(data_card, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        columns = ("etapa", "neurosky", "emotion", "eye", "heart_rate", "cuestionario", "enunciado", "escrito")
        self.session_data_tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings", height=4, selectmode="none",
        )
        for col, label, width in (
            ("etapa", "Etapa", scaled(70)),
            ("neurosky", "NeuroSky", scaled(100)),
            ("emotion", "Emotion", scaled(100)),
            ("eye", "Mirada (izq/der)", scaled(170)),
            ("heart_rate", "Frecuencia cardíaca", scaled(190)),
            ("cuestionario", "Cuestionario", scaled(120)),
            ("enunciado", "Enunciado (aperturas)", scaled(170)),
            ("escrito", "Escrito Etapa 3", scaled(110)),
        ):
            self.session_data_tree.heading(col, text=label, anchor="center")
            self.session_data_tree.column(col, width=width, anchor="center")
        self.session_data_tree.grid(row=0, column=0, sticky="nsew")

        h_scrollbar = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.session_data_tree.xview)
        self.session_data_tree.configure(xscrollcommand=h_scrollbar.set)
        h_scrollbar.grid(row=1, column=0, sticky="ew")

        # ---------------- Dataset consolidado (ver data/build_dataset.py) ----------------
        # A diferencia de "Datos guardados" (un desafio, un participante),
        # esto junta en un solo CSV los datos crudos de TODOS los
        # participantes/desafios/etapas ya exportados -- se genera bajo
        # demanda (recorre el Escritorio entero) y se previsualiza aca antes
        # de usarlo para el analisis.
        dataset_card = ctk.CTkFrame(wrapper, fg_color=BG_CARD, corner_radius=12)
        dataset_card.pack(fill="x")

        ctk.CTkLabel(
            dataset_card, text="🧬  Dataset consolidado",
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(13), weight="bold"),
        ).pack(anchor="w", padx=18, pady=(16, 4))
        ctk.CTkLabel(
            dataset_card,
            text="Une en un solo CSV los datos crudos de TODOS los participantes y desafíos ya "
                 "exportados: NeuroSky (bandas EEG), Emotion Tracker (emoción dominante + el "
                 "porcentaje de cada categoría), Eye Tracker (mirada + izq/der agregado), "
                 "frecuencia cardíaca del reloj y resultado de los cuestionarios -- una fila por "
                 "etapa de cada desafío.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(11)), text_color=TEXT_MUTED,
            wraplength=wrap(820), justify="left",
        ).pack(anchor="w", padx=18, pady=(0, 10))

        controls_row = ctk.CTkFrame(dataset_card, fg_color="transparent")
        controls_row.pack(fill="x", padx=18, pady=(0, 18))
        self.dataset_generate_button = ctk.CTkButton(
            controls_row, text="🔄  Generar / actualizar dataset", height=scaled(34), corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12)),
            fg_color=BG_CARD_ALT, hover_color=BORDER,
            command=self._generate_dataset,
        )
        self.dataset_generate_button.pack(side="left")
        # Deshabilitado hasta la primera generacion exitosa de esta sesion de
        # la app -- la tabla completa se ve en una ventana aparte a pantalla
        # completa (ver _open_dataset_window), no incrustada aca: con
        # decenas de columnas (listas de lecturas crudas, etc.) una vista
        # incrustada quedaba demasiado chica para detallar nada.
        self.dataset_view_button = ctk.CTkButton(
            controls_row, text="🖥️  Ver dataset completo", height=scaled(34), corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12), weight="bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            state="disabled", command=self._open_dataset_window,
        )
        self.dataset_view_button.pack(side="left", padx=(8, 0))
        self._last_dataset_df: Optional[pd.DataFrame] = None
        self._last_dataset_path: Optional[Path] = None
        self._dataset_window: Optional[ctk.CTkToplevel] = None
        self._dataset_tree: Optional[ttk.Treeview] = None

        self.dataset_status_label = ctk.CTkLabel(
            dataset_card, text="Todavía no se generó en esta sesión de la app.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(11)), text_color=TEXT_MUTED,
            wraplength=wrap(820), justify="left",
        )
        self.dataset_status_label.pack(anchor="w", padx=18, pady=(0, 18))

        self._refresh_session_tab()
        self._refresh_session_data_matrix()

    def _guided_session_button_text(self) -> str:
        active = self.store.get_active()
        if active is None:
            return "🚀  Iniciar sesión guiada"
        return f"🚀  Iniciar sesión guiada con el {participant_label(active)}"

    def _refresh_session_data_matrix(self):
        """Recalcula la matriz de "Datos guardados" del desafío elegido,
        para el participante activo -- lee siempre de disco (nunca de
        estado en memoria de la sesion guiada), asi que sirve igual si la
        app se reinicio o si el participante viene de otra sesion. Nunca
        rompe la interfaz: si falta la carpeta, un archivo, o el CSV esta
        corrupto, la celda correspondiente queda en "—" (ver
        stage_capture.summarize_stage)."""
        tree = getattr(self, "session_data_tree", None)
        if tree is None:
            return
        tree.delete(*tree.get_children())

        placeholder = ("—",) * 7
        participant = self.store.get_active()
        if participant is None:
            for stage in GUIDED_SESSION_STAGE_ORDER:
                tree.insert("", "end", values=(f"Etapa {stage}", *placeholder))
            return

        try:
            challenge_number = int(self.session_data_challenge_menu.get())
        except (ValueError, AttributeError):
            challenge_number = 1
        folder = challenge_dir_readonly(participant, challenge_number)

        for stage in GUIDED_SESSION_STAGE_ORDER:
            try:
                summary = summarize_stage(folder, stage)
            except Exception:
                summary = {}
            tree.insert(
                "", "end",
                values=(
                    f"Etapa {stage}",
                    summary.get("neurosky", "—"), summary.get("emotion", "—"), summary.get("eye", "—"),
                    summary.get("heart_rate", "—"), summary.get("cuestionario", "—"),
                    summary.get("enunciado", "—"), summary.get("escrito", "—"),
                ),
            )

    def _refresh_session_tab(self):
        active = self.store.get_active()
        self.guided_session_button.configure(
            text=self._guided_session_button_text(), state="normal" if active else "disabled",
        )

    # ---------------- Dataset consolidado ----------------
    def _generate_dataset(self):
        """Dispara build_dataset.save_dataset() en un hilo aparte -- recorre
        TODO ~/Escritorio/Sesiones_participantes/, asi que con muchas
        sesiones puede tardar unos segundos y no debe congelar la UI."""
        self.dataset_generate_button.configure(state="disabled", text="Generando...")
        self.dataset_status_label.configure(
            text="Generando dataset (leyendo todas las sesiones exportadas)...", text_color=TEXT_MUTED,
        )
        threading.Thread(target=self._run_dataset_generation, daemon=True).start()

    def _run_dataset_generation(self):
        try:
            df, path = save_dataset()
            error = ""
        except Exception as exc:
            df, path, error = None, None, str(exc)
        self.after(0, lambda: self._on_dataset_generated(df, path, error))

    def _on_dataset_generated(self, df, path, error: str):
        self.dataset_generate_button.configure(state="normal", text="🔄  Generar / actualizar dataset")
        if error:
            self.dataset_status_label.configure(text=f"⚠️  No se pudo generar: {error}", text_color=WARNING)
            self.dataset_view_button.configure(state="disabled")
            return

        self._last_dataset_df, self._last_dataset_path = df, path
        if df.empty:
            self.dataset_status_label.configure(
                text="No se encontraron sesiones guiadas exportadas todavía en "
                     "Escritorio/Sesiones_participantes.",
                text_color=TEXT_MUTED,
            )
            self.dataset_view_button.configure(state="disabled")
            return

        self.dataset_status_label.configure(
            text=f"✅  {len(df)} filas · {len(df.columns)} columnas · guardado en {path}",
            text_color=TEXT_MUTED,
        )
        self.dataset_view_button.configure(state="normal")
        if self._dataset_window is not None:
            self._fill_dataset_tree(self._dataset_tree, df)  # ventana ya abierta -- refrescarla en el momento

    def _open_dataset_window(self):
        """Ventana aparte, maximizada a pantalla completa, con el dataset
        entero (todas las filas, todas las columnas) -- la vista incrustada
        en la tarjeta se quedaba corta para un dataset de decenas de
        columnas (listas de lecturas crudas, el prompt de la Etapa 3,
        etc.). Si ya está abierta, la trae al frente en vez de duplicarla."""
        if self._last_dataset_df is None or self._last_dataset_df.empty:
            return
        if self._dataset_window is not None:
            try:
                self._dataset_window.deiconify()
                self._dataset_window.lift()
                self._dataset_window.focus_force()
                return
            except Exception:
                self._dataset_window = None

        window = ctk.CTkToplevel(self)
        window.title(f"Dataset consolidado -- {self._last_dataset_path}")
        # Geometry al tamaño de pantalla como base (siempre funciona) +
        # "maximizado" nativo del sistema operativo si está disponible --
        # "-zoomed" no existe en todos los window managers de Linux, así
        # que no debe romper la ventana si el intento falla.
        window.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")
        try:
            if sys.platform.startswith("win"):
                window.state("zoomed")
            else:
                window.attributes("-zoomed", True)
        except Exception:
            pass
        window.configure(fg_color=BG_APP)

        header = ctk.CTkFrame(window, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 8))
        ctk.CTkLabel(
            header, text=f"🧬  Dataset consolidado · {len(self._last_dataset_df)} filas · "
                         f"{len(self._last_dataset_df.columns)} columnas",
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(16), weight="bold"),
        ).pack(side="left")
        ctk.CTkButton(
            header, text="Cerrar", width=scaled(100), height=scaled(32), corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12)),
            fg_color=BG_CARD_ALT, hover_color=BORDER,
            command=window.destroy,
        ).pack(side="right")

        tree_frame = ctk.CTkFrame(window, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        tree = ttk.Treeview(tree_frame, show="headings", selectmode="none")
        tree.grid(row=0, column=0, sticky="nsew")
        v_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=v_scrollbar.set)
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
        tree.configure(xscrollcommand=h_scrollbar.set)
        h_scrollbar.grid(row=1, column=0, sticky="ew")

        self._fill_dataset_tree(tree, self._last_dataset_df)

        def on_close():
            self._dataset_window = None
            self._dataset_tree = None
            window.destroy()

        window.protocol("WM_DELETE_WINDOW", on_close)
        self._dataset_window = window
        self._dataset_tree = tree

    @staticmethod
    def _fill_dataset_tree(tree: ttk.Treeview, df):
        """Todas las filas y columnas del dataset -- a diferencia de la
        vieja vista incrustada, acá no hace falta truncar ni limitar
        filas: la ventana tiene todo el ancho/alto de la pantalla para
        detallar los datos."""
        tree.delete(*tree.get_children())
        columns = list(df.columns)
        tree["columns"] = columns
        for col in columns:
            tree.heading(col, text=col, anchor="center")
            tree.column(col, width=scaled(180), anchor="center", stretch=False)
        for _, row in df.iterrows():
            values = ["" if pd.isna(row[col]) else str(row[col]) for col in columns]
            tree.insert("", "end", values=values)


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
