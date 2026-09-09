"""GUI principal: lanzador de juegos + gestion de participantes."""

import threading
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
from collections import Counter
from pathlib import Path
from tkinter import ttk

import customtkinter as ctk

from challenges import get_challenge
from difficulty import get_difficulty
from game_launcher import (
    PROJECT_ROOT,
    discover_games,
    import_heart_rate,
    open_in_vscode,
    play_game,
    read_combined_session_data,
    repair_environment,
    start_emotion_tracker,
)
from participant_store import ParticipantStore, participant_file_stub, participant_label
from personal_records import save_personal_record
from session_store import SessionStore
from session_wizard import SessionWizard
from statement_view import render_statement

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_FILE = DATA_DIR / "participants.json"
SESSIONS_FILE = DATA_DIR / "sessions.json"

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


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Panel de Experimento")
        self.geometry("1080x680")
        self.minsize(920, 580)
        self.configure(fg_color=BG_APP)
        _enable_linux_wheel_scroll(self)
        # La app arranca ya maximizada (pedido explicito) en vez del tamano
        # fijo de arriba, que queda solo como base/minsize.
        self.after(0, self._maximize)

        self.store = ParticipantStore(DATA_FILE)
        self.session_store = SessionStore(SESSIONS_FILE)
        self.emotion_process = None
        self.emotion_participant_id = None
        self.active_session = None
        self.selected_session = None
        self.sort_games_by_difficulty = False

        # Si la app se cerro con una sesion sin terminar, la recuperamos para
        # poder cerrarla bien (no se relanza la camara automaticamente).
        active_participant = self.store.get_active()
        if active_participant is not None:
            self.active_session = self.session_store.get_open_session(active_participant["id"])

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
        # La app entera arranca maximizada (ver __init__); esto solo
        # cubre el caso de que el usuario la haya desmaximizado a mano.
        self._maximize()
        self.session_wizard_frame.tkraise()
        self.session_wizard.start()

    def exit_session_wizard(self):
        self.session_wizard_frame.lower()
        self._select_nav("session")
        # No se restaura ningun tamano "chico": la ventana siempre vive
        # maximizada, asi que simplemente se deja como esta (evita el bug
        # de que forzar state("normal") + geometry la dejaba minimizada).

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
        sidebar = ctk.CTkFrame(self, width=230, corner_radius=0, fg_color=BG_SIDEBAR)
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_propagate(False)

        brand = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand.pack(fill="x", padx=20, pady=(26, 30))
        ctk.CTkLabel(
            brand, text="🎮 Vibe Coding", font=ctk.CTkFont(family=FONT_FAMILY, size=19, weight="bold")
        ).pack(anchor="w")
        ctk.CTkLabel(
            brand, text="Panel de experimento", font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=TEXT_MUTED,
        ).pack(anchor="w", pady=(2, 0))

        nav = ctk.CTkFrame(sidebar, fg_color="transparent")
        nav.pack(fill="x", padx=14)

        self._nav_buttons["games"] = self._nav_button(nav, "🕹️  Juegos", "games")
        self._nav_buttons["participants"] = self._nav_button(nav, "🧑‍🤝‍🧑  Participantes", "participants")
        self._nav_buttons["session"] = self._nav_button(nav, "⏱️  Sesión", "session")

        footer = ctk.CTkFrame(sidebar, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=20, pady=18)

        self.tracker_card = ctk.CTkFrame(footer, fg_color=BG_CARD, corner_radius=8)
        self.tracker_card.pack(fill="x", pady=(0, 12))
        self.tracker_status_label = ctk.CTkLabel(
            self.tracker_card, text="🎥  Seguimiento: inactivo", font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=TEXT_MUTED, anchor="w", justify="left", wraplength=180,
        )
        self.tracker_status_label.pack(anchor="w", padx=10, pady=(10, 4))
        self.tracker_stop_button = ctk.CTkButton(
            self.tracker_card, text="Detener", height=26, width=90, corner_radius=6,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            fg_color="transparent", hover_color=DANGER, border_width=1, border_color=DANGER,
            text_color=DANGER, state="disabled",
            command=self._stop_emotion_tracker,
        )
        self.tracker_stop_button.pack(anchor="w", padx=10, pady=(0, 10))

        ctk.CTkLabel(
            footer, text=f"Proyecto: {PROJECT_ROOT.name}", font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            text_color=TEXT_MUTED, wraplength=190, justify="left",
        ).pack(anchor="w")

    def _nav_button(self, parent, text, key):
        btn = ctk.CTkButton(
            parent,
            text=text,
            anchor="w",
            corner_radius=8,
            height=42,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
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

    # ---------------- Juegos ----------------
    def _build_games_tab(self):
        header = ctk.CTkFrame(self.tab_games, fg_color="transparent")
        header.pack(fill="x", padx=26, pady=(24, 6))

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            title_box, text="Juegos", font=ctk.CTkFont(family=FONT_FAMILY, size=22, weight="bold")
        ).pack(anchor="w")
        self.active_label = ctk.CTkLabel(
            title_box, text=self._active_label_text(), font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=TEXT_MUTED,
        )
        self.active_label.pack(anchor="w", pady=(2, 0))

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right")

        self.repair_button = ctk.CTkButton(
            actions, text="🛠️  Reparar entorno", width=160, height=34, corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=WARNING, hover_color=WARNING_HOVER, text_color="#1a1a1a",
            command=self._repair_environment,
        )
        self.repair_button.pack(side="left", padx=(0, 8))

        self.difficulty_button = ctk.CTkButton(
            actions, text="📊  Ver juegos en dificultad", width=210, height=34, corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=BG_CARD_ALT, hover_color=BORDER, text_color="white",
            command=self._toggle_difficulty_view,
        )
        self.difficulty_button.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            actions, text="🔄  Actualizar", width=130, height=34, corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
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
                title_row, text=f"🎲  {main_text}", font=ctk.CTkFont(family=FONT_FAMILY, size=15, weight="bold")
            ).pack(side="left")
            if sub_text and sub_text != main_text:
                ctk.CTkLabel(
                    title_row, text=f"   ·   {sub_text}",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=13), text_color=TEXT_MUTED,
                ).pack(side="left")

            pills_row = ctk.CTkFrame(info, fg_color="transparent")
            pills_row.pack(anchor="w", pady=(6, 0))

            if game.is_playable:
                pill_text, pill_bg, pill_fg = "● Listo para jugar", "#1c3a26", "#4ade80"
            else:
                pill_text, pill_bg, pill_fg = "● Sin main.py", "#332a1c", "#c9a15a"
            ctk.CTkLabel(
                pills_row, text=pill_text, font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
                fg_color=pill_bg, text_color=pill_fg, corner_radius=10, padx=10, pady=2,
            ).pack(side="left")

            difficulty = get_difficulty(game.name)
            if difficulty:
                diff_bg, diff_fg = self._difficulty_colors(difficulty.tier)
                ctk.CTkLabel(
                    pills_row, text=f"🎯 {difficulty.rank}/7 · {difficulty.tier}",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
                    fg_color=diff_bg, text_color=diff_fg, corner_radius=10, padx=10, pady=2,
                ).pack(side="left", padx=(8, 0))

            buttons = ctk.CTkFrame(card, fg_color="transparent")
            buttons.grid(row=0, column=1, sticky="e", padx=18, pady=14)

            ctk.CTkButton(
                buttons, text="📝  VS Code", width=130, height=34, corner_radius=8,
                font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                fg_color=BG_CARD_ALT, hover_color=BORDER, text_color="white",
                command=lambda g=game: self._open_vscode(g),
            ).pack(side="left", padx=(0, 8))

            statement_btn = ctk.CTkButton(
                buttons, text="📄  Ver enunciado del desafío", width=210, height=34, corner_radius=8,
                font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                fg_color=BG_CARD_ALT, hover_color=BORDER, text_color="white",
                command=lambda g=game: self._show_statement_modal(g),
            )
            statement_btn.pack(side="left", padx=(0, 8))
            if get_challenge(game.name) is None:
                statement_btn.configure(state="disabled", text_color=TEXT_MUTED)

            play_btn = ctk.CTkButton(
                buttons, text="▶  Jugar", width=110, height=34, corner_radius=8,
                font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
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
        modal.geometry("760x680")
        modal.configure(fg_color=BG_APP)
        modal.transient(self)
        modal.wait_visibility()
        modal.grab_set()

        header = ctk.CTkFrame(modal, fg_color="transparent")
        header.pack(fill="x", padx=26, pady=(20, 6))
        ctk.CTkLabel(
            header, text=challenge.title,
            font=ctk.CTkFont(family=FONT_FAMILY, size=18, weight="bold"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text="Esto es exactamente lo que va a ver el participante en la Etapa 1 de la sesión guiada.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12), text_color=TEXT_MUTED,
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
            wraplength=680,
        )

        ctk.CTkButton(
            modal, text="Cerrar", height=36, width=120, corner_radius=8,
            fg_color=BG_CARD_ALT, hover_color=BORDER, command=modal.destroy,
        ).pack(pady=(0, 18))

    def _open_vscode(self, game):
        try:
            open_in_vscode(game)
        except FileNotFoundError:
            messagebox.showerror(
                "VS Code no encontrado",
                "No se encontro el comando 'code' en el PATH. Instala el CLI de VS Code e intenta de nuevo.",
            )
            return

        active = self.store.get_active()
        if active is not None:
            self._ensure_emotion_tracker(active, session_label=game.display_name)

    def _ensure_emotion_tracker(self, participant, session_label):
        # Ya hay un tracker corriendo para este mismo participante: no duplicar proceso de camara.
        if self.emotion_process is not None and self.emotion_process.poll() is None:
            if self.emotion_participant_id == participant["id"]:
                return
            self._stop_emotion_tracker()

        try:
            self.emotion_process = start_emotion_tracker(participant, session_label)
        except FileNotFoundError as exc:
            messagebox.showerror("No se pudo iniciar el seguimiento emocional", str(exc))
            return

        self.emotion_participant_id = participant["id"]
        self._update_tracker_status(
            f"🎥  Seguimiento: activo\n{participant_label(participant)} · {session_label}",
            active=True,
        )

    def _stop_emotion_tracker(self):
        if self.emotion_process is not None and self.emotion_process.poll() is None:
            self.emotion_process.terminate()
        self.emotion_process = None
        self.emotion_participant_id = None
        self._update_tracker_status("🎥  Seguimiento: inactivo", active=False)

    def _update_tracker_status(self, text, active: bool):
        self.tracker_status_label.configure(text=text, text_color="#4ade80" if active else TEXT_MUTED)
        self.tracker_stop_button.configure(state="normal" if active else "disabled")

    def _on_close(self):
        self._stop_emotion_tracker()
        self.destroy()

    def _repair_environment(self):
        self.repair_button.configure(state="disabled", text="Reparando...")

        log_win = ctk.CTkToplevel(self)
        log_win.title("Reparando entorno (.venv)")
        log_win.geometry("620x400")
        log_win.configure(fg_color=BG_APP)
        log_win.transient(self)

        ctk.CTkLabel(
            log_win, text="🛠️  Reinstalando dependencias en el .venv unificado",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
        ).pack(anchor="w", padx=14, pady=(14, 6))

        textbox = ctk.CTkTextbox(
            log_win, wrap="word", font=ctk.CTkFont(family="monospace", size=11),
            fg_color=BG_CARD, corner_radius=10,
        )
        textbox.pack(fill="both", expand=True, padx=14, pady=(0, 8))

        close_btn = ctk.CTkButton(
            log_win, text="Cerrar", state="disabled", width=120, corner_radius=8,
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
                    append_line("\n>> Ocurrio un error reparando el entorno. Revisa el log.")
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
                "No hay un participante activo seleccionado. Deseas iniciar el juego de todas formas?",
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
            title_row, text="Participantes", font=ctk.CTkFont(family=FONT_FAMILY, size=22, weight="bold")
        ).pack(side="left")
        self.participant_count_label = ctk.CTkLabel(
            title_row, text=self._participant_count_text(),
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=BG_CARD_ALT, corner_radius=10, text_color="#c9cdd9", padx=12, pady=4,
        )
        self.participant_count_label.pack(side="right")
        ctk.CTkLabel(
            wrapper, text="Registra sujetos de prueba y selecciona el participante activo de la sesion.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12), text_color=TEXT_MUTED,
        ).pack(anchor="w", pady=(2, 14))

        container = ctk.CTkFrame(wrapper, fg_color="transparent")
        container.pack(fill="both", expand=True)
        container.grid_columnconfigure(1, weight=1)
        container.grid_rowconfigure(0, weight=1)

        form = ctk.CTkFrame(container, fg_color=BG_CARD, corner_radius=12)
        form.grid(row=0, column=0, sticky="nsw", padx=(0, 14))

        ctk.CTkLabel(
            form, text="➕  Nuevo participante", font=ctk.CTkFont(family=FONT_FAMILY, size=15, weight="bold")
        ).pack(anchor="w", padx=18, pady=(18, 8))
        ctk.CTkLabel(
            form,
            text="Dentro de la app cada participante es anónimo\n(Participante 1, Participante 2, ...). El nombre y\napellido que pidas al agregarlo se guardan aparte,\nen tu Escritorio, no en los datos de la sesión.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11), text_color=TEXT_MUTED,
            justify="left",
        ).pack(anchor="w", padx=18, pady=(0, 16))

        ctk.CTkButton(
            form, text="💾  Agregar participante", height=36, corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._open_add_participant_modal,
        ).pack(fill="x", padx=18, pady=(8, 8))
        ctk.CTkButton(
            form, text="✅  Marcar como activo", height=36, corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=SUCCESS, hover_color=SUCCESS_HOVER,
            command=self._mark_selected_active,
        ).pack(fill="x", padx=18, pady=(0, 8))
        ctk.CTkButton(
            form, text="🗑️  Eliminar seleccionado", height=36, corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color="transparent", hover_color=DANGER, border_width=1, border_color=DANGER,
            text_color=DANGER,
            command=self._delete_selected,
        ).pack(fill="x", padx=18, pady=(0, 18))

        table_frame = ctk.CTkFrame(container, fg_color=BG_CARD, corner_radius=12)
        table_frame.grid(row=0, column=1, sticky="nsew")
        table_frame.grid_rowconfigure(1, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        self.participants_active_label = ctk.CTkLabel(
            table_frame, text=self._active_label_text(), font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=BG_CARD_ALT, corner_radius=8, anchor="w",
        )
        self.participants_active_label.grid(row=0, column=0, columnspan=2, sticky="ew", padx=16, pady=(16, 10), ipady=6)

        self._style_treeview()

        columns = ("participante", "nivel", "fecha")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        for col, label, width in (
            ("participante", "Participante", 160),
            ("nivel", "Nivel de experiencia", 220),
            ("fecha", "Registrado", 180),
        ):
            self.tree.heading(col, text=label, anchor="center")
            self.tree.column(col, width=width, anchor="center")
        self.tree.grid(row=1, column=0, sticky="nsew", padx=(16, 0), pady=(0, 16))

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
            rowheight=30,
            font=(FONT_FAMILY, 11),
        )
        style.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", "white")])
        style.configure(
            "Treeview.Heading",
            background=BG_CARD,
            foreground=TEXT_MUTED,
            borderwidth=0,
            relief="flat",
            font=(FONT_FAMILY, 11, "bold"),
        )
        style.map("Treeview.Heading", background=[("active", BG_CARD)])
        style.configure("Vertical.TScrollbar", background=BG_CARD_ALT, troughcolor=BG_CARD, bordercolor=BG_CARD)

    def _refresh_participants(self):
        self.tree.delete(*self.tree.get_children())
        for p in self.store.list_participants():
            nivel = p.get("attributes", {}).get("nivel_experiencia", "—")
            self.tree.insert("", "end", iid=p["id"], values=(participant_label(p), nivel, p["created_at"]))
        self.active_label.configure(text=self._active_label_text())
        self.participants_active_label.configure(text=self._active_label_text())
        self.participant_count_label.configure(text=self._participant_count_text())
        count = len(self.store.list_participants())
        self._nav_buttons["participants"].configure(text=f"🧑‍🤝‍🧑  Participantes ({count})")

    def _open_add_participant_modal(self):
        modal = ctk.CTkToplevel(self)
        modal.title("Nuevo participante")
        modal.geometry("400x420")
        modal.configure(fg_color=BG_APP)
        modal.transient(self)
        modal.resizable(False, False)
        # grab_set() debe esperar a que la ventana ya este dibujada en pantalla,
        # si no lanza "grab failed: window not viewable".
        modal.wait_visibility()
        modal.grab_set()

        ctk.CTkLabel(
            modal, text="➕  Nuevo participante",
            font=ctk.CTkFont(family=FONT_FAMILY, size=18, weight="bold"),
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
            font=ctk.CTkFont(family=FONT_FAMILY, size=11), text_color=TEXT_MUTED, justify="center",
        ).pack(padx=24, pady=(0, 16))

        entry_nombre = ctk.CTkEntry(
            modal, width=260, height=34, corner_radius=8, fg_color=BG_CARD_ALT, border_width=0,
            placeholder_text="Nombre",
        )
        entry_nombre.pack(pady=(0, 10))
        entry_apellido = ctk.CTkEntry(
            modal, width=260, height=34, corner_radius=8, fg_color=BG_CARD_ALT, border_width=0,
            placeholder_text="Apellido",
        )
        entry_apellido.pack(pady=(0, 14))
        entry_nombre.focus_set()

        ctk.CTkLabel(
            modal, text="Nivel de experiencia", font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=TEXT_MUTED,
        ).pack(anchor="center")
        experience_menu = ctk.CTkOptionMenu(
            modal, width=260, height=34, corner_radius=8,
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
            buttons_row, text="Cancelar", width=110, height=36, corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color="transparent", hover_color=BORDER, border_width=1, border_color=BORDER,
            command=modal.destroy,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            buttons_row, text="Guardar", width=110, height=36, corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=on_accept,
        ).pack(side="left")

    def _selected_id(self):
        selection = self.tree.selection()
        return selection[0] if selection else None

    def _mark_selected_active(self):
        pid = self._selected_id()
        if not pid:
            messagebox.showinfo("Sin seleccion", "Selecciona un participante de la tabla primero.")
            return
        self.store.set_active(pid)
        self._refresh_participants()
        self._refresh_session_tab()

    def _delete_selected(self):
        pid = self._selected_id()
        if not pid:
            messagebox.showinfo("Sin seleccion", "Selecciona un participante de la tabla primero.")
            return
        if messagebox.askyesno("Confirmar", "Eliminar este participante?"):
            self.store.delete_participant(pid)
            self._refresh_participants()

    # ---------------- Sesion ----------------
    def _build_session_tab(self):
        wrapper = ctk.CTkFrame(self.tab_session, fg_color="transparent")
        wrapper.pack(fill="both", expand=True, padx=26, pady=(24, 20))

        ctk.CTkLabel(
            wrapper, text="Sesión", font=ctk.CTkFont(family=FONT_FAMILY, size=22, weight="bold")
        ).pack(anchor="w")
        ctk.CTkLabel(
            wrapper,
            text="Inicia/termina la sesión del participante activo, importa el BPM del reloj "
                 "y revisa emociones y frecuencia cardíaca juntos.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12), text_color=TEXT_MUTED,
        ).pack(anchor="w", pady=(2, 14))

        control_card = ctk.CTkFrame(wrapper, fg_color=BG_CARD, corner_radius=12)
        control_card.pack(fill="x", pady=(0, 14))

        self.session_active_label = ctk.CTkLabel(
            control_card, text=self._active_label_text(),
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
        )
        self.session_active_label.pack(anchor="w", padx=18, pady=(16, 4))

        self.session_status_label = ctk.CTkLabel(
            control_card, text="Sin sesión activa.", font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=TEXT_MUTED,
        )
        self.session_status_label.pack(anchor="w", padx=18, pady=(0, 12))

        buttons_row = ctk.CTkFrame(control_card, fg_color="transparent")
        buttons_row.pack(anchor="w", padx=18, pady=(0, 18))

        self.start_session_button = ctk.CTkButton(
            buttons_row, text="▶  Iniciar sesión", height=36, width=160, corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=SUCCESS, hover_color=SUCCESS_HOVER,
            command=self._open_start_session_modal,
        )
        self.start_session_button.pack(side="left", padx=(0, 8))

        self.end_session_button = ctk.CTkButton(
            buttons_row, text="⏹  Terminar sesión", height=36, width=160, corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color="transparent", hover_color=DANGER, border_width=1, border_color=DANGER,
            text_color=DANGER, state="disabled",
            command=self._end_session,
        )
        self.end_session_button.pack(side="left", padx=(0, 8))

        self.import_hr_button = ctk.CTkButton(
            buttons_row, text="📥  Importar datos del reloj", height=36, width=210, corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=BG_CARD_ALT, hover_color=BORDER, text_color="white",
            command=self._import_heart_rate,
        )
        self.import_hr_button.pack(side="left")

        guided_card = ctk.CTkFrame(wrapper, fg_color=BG_CARD, corner_radius=12)
        guided_card.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(
            guided_card, text="🚀  Sesión guiada de desafíos",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
        ).pack(anchor="w", padx=18, pady=(16, 4))
        ctk.CTkLabel(
            guided_card,
            text="Reemplaza toda la interfaz por un asistente de 3 etapas para el "
                 "participante activo: enunciado del problema, prompt del participante "
                 "y resultado de Claude Code, empezando por el desafío más fácil.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12), text_color=TEXT_MUTED,
            wraplength=760, justify="left",
        ).pack(anchor="w", padx=18, pady=(0, 12))
        self.guided_session_button = ctk.CTkButton(
            guided_card, text="🚀  Comenzar sesión guiada", height=36, width=220, corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self.enter_session_wizard,
        )
        self.guided_session_button.pack(anchor="w", padx=18, pady=(0, 18))

        table_card = ctk.CTkFrame(wrapper, fg_color=BG_CARD, corner_radius=12)
        table_card.pack(fill="both", expand=True)
        table_card.grid_rowconfigure(2, weight=1)
        table_card.grid_columnconfigure(0, weight=1)

        selector_row = ctk.CTkFrame(table_card, fg_color="transparent")
        selector_row.grid(row=0, column=0, columnspan=2, sticky="ew", padx=16, pady=(16, 8))
        ctk.CTkLabel(
            selector_row, text="Sesión a mostrar:", font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=TEXT_MUTED,
        ).pack(side="left", padx=(0, 8))
        self.session_selector = ctk.CTkOptionMenu(
            selector_row, values=["(sin sesiones)"], width=340, height=30,
            fg_color=BG_CARD_ALT, button_color=BORDER, button_hover_color=ACCENT,
            command=self._on_session_selected,
        )
        self.session_selector.pack(side="left", padx=(0, 14))
        self.session_participant_label = ctk.CTkLabel(
            selector_row, text="", font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color="#c9cdd9",
        )
        self.session_participant_label.pack(side="left")

        self.session_stats_label = ctk.CTkLabel(
            table_card, text="", font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=BG_CARD_ALT, corner_radius=8, anchor="w", justify="left",
        )
        self.session_stats_label.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 10), ipady=8)

        columns = ("hora", "tipo", "valor")
        self.session_tree = ttk.Treeview(table_card, columns=columns, show="headings", selectmode="browse")
        for col, label, width in (("hora", "Hora", 160), ("tipo", "Tipo", 100), ("valor", "Valor", 160)):
            self.session_tree.heading(col, text=label, anchor="center")
            self.session_tree.column(col, width=width, anchor="center")
        self.session_tree.grid(row=2, column=0, sticky="nsew", padx=(16, 0), pady=(0, 16))

        session_scrollbar = ttk.Scrollbar(table_card, orient="vertical", command=self.session_tree.yview)
        self.session_tree.configure(yscrollcommand=session_scrollbar.set)
        session_scrollbar.grid(row=2, column=1, sticky="ns", padx=(0, 16), pady=(0, 16))

        self._refresh_session_tab()

    def _open_start_session_modal(self):
        active = self.store.get_active()
        if active is None:
            messagebox.showinfo(
                "Sin participante activo",
                "Selecciona un participante activo en la pestaña Participantes primero.",
            )
            return
        if self.active_session is not None:
            messagebox.showinfo("Sesión en curso", "Ya hay una sesión activa. Termínala antes de iniciar otra.")
            return

        modal = ctk.CTkToplevel(self)
        modal.title("Activar reloj")
        modal.geometry("400x240")
        modal.configure(fg_color=BG_APP)
        modal.transient(self)
        modal.resizable(False, False)
        # grab_set() debe esperar a que la ventana ya este dibujada en pantalla,
        # si no lanza "grab failed: window not viewable".
        modal.wait_visibility()
        modal.grab_set()

        ctk.CTkLabel(
            modal, text="⌚  Activar reloj",
            font=ctk.CTkFont(family=FONT_FAMILY, size=18, weight="bold"),
        ).pack(pady=(26, 10))
        ctk.CTkLabel(
            modal,
            text=(
                "Inicia ahora el ejercicio en el reloj\n"
                "(Samsung Health → Ejercicio → tipo sin GPS).\n\n"
                "Cuando el reloj ya esté midiendo,\n"
                "presiona Aceptar para marcar el inicio\n"
                "exacto de la sesión."
            ),
            font=ctk.CTkFont(family=FONT_FAMILY, size=12), text_color=TEXT_MUTED, justify="center",
        ).pack(padx=24, pady=(0, 20))

        def on_accept():
            session = self.session_store.start_session(active["id"], label="sesion")
            self.active_session = session
            self._ensure_emotion_tracker(active, session_label="sesion")
            self._refresh_session_tab()
            modal.destroy()

        ctk.CTkButton(
            modal, text="Aceptar", height=38, width=160, corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            fg_color=SUCCESS, hover_color=SUCCESS_HOVER,
            command=on_accept,
        ).pack()

    def _end_session(self):
        if self.active_session is None:
            return
        self.session_store.end_session(self.active_session["id"])
        self._stop_emotion_tracker()
        self.active_session = None
        self._refresh_session_tab()
        messagebox.showinfo("Sesión terminada", "La sesión se guardó. Ya puedes importar los datos del reloj.")

    def _import_heart_rate(self):
        active = self.store.get_active()
        if active is None:
            messagebox.showinfo("Sin participante activo", "Selecciona un participante activo primero.")
            return
        if self.selected_session is None:
            messagebox.showinfo("Sin sesión seleccionada", "Selecciona una sesión terminada en el desplegable.")
            return
        if self.selected_session.get("end_time") is None:
            messagebox.showinfo("Sesión en curso", "Termina la sesión antes de importar sus datos.")
            return

        default_dir = Path.home() / "Escritorio" / "Datos_Biometricos"
        export_dir = filedialog.askdirectory(
            title="Entra a la carpeta del export (ej. PARTICIPANTE_1) y selecciónala",
            initialdir=str(default_dir) if default_dir.exists() else str(Path.home()),
        )
        if not export_dir:
            return

        expected_stub = participant_file_stub(active)
        folder_name = Path(export_dir).name.strip().upper()
        if folder_name != expected_stub:
            messagebox.showerror(
                "La carpeta no coincide con el participante",
                f"El participante activo es {participant_label(active)}, así que la "
                f"carpeta del export debe llamarse exactamente \"{expected_stub}\".\n\n"
                f"Seleccionaste \"{Path(export_dir).name}\", que no coincide. Renombra la carpeta "
                "exportada o verifica que sea la del participante correcto antes de importar.",
            )
            return

        try:
            log_file, count = import_heart_rate(active, self.selected_session, Path(export_dir))
        except FileNotFoundError as exc:
            messagebox.showerror("No se pudo importar", str(exc))
            return

        if count == 0:
            messagebox.showwarning(
                "Sin lecturas en esa ventana",
                "No se encontraron muestras BPM dentro del rango de tiempo de la sesión seleccionada. "
                "Verifica que el ejercicio en el reloj haya coincidido con la sesión.",
            )
        else:
            messagebox.showinfo("Datos importados", f"{count} lecturas de BPM guardadas en:\n{log_file}")

        self._refresh_session_view()

    def _on_session_selected(self, label: str):
        active = self.store.get_active()
        if not active:
            return
        for s in self.session_store.list_sessions(active["id"]):
            if self._session_label(s) == label:
                self.selected_session = s
                break
        self._refresh_session_view()

    @staticmethod
    def _session_label(session: dict) -> str:
        end = session.get("end_time") or "en curso"
        return f"{session['start_time']} → {end}"

    def _refresh_session_tab(self):
        active = self.store.get_active()
        self.session_active_label.configure(text=self._active_label_text())

        if self.active_session is not None:
            self.session_status_label.configure(
                text=f"🟢 Sesión en curso, iniciada a las {self.active_session['start_time']}",
                text_color="#4ade80",
            )
            self.start_session_button.configure(state="disabled")
            self.end_session_button.configure(state="normal")
        else:
            self.session_status_label.configure(text="Sin sesión activa.", text_color=TEXT_MUTED)
            self.start_session_button.configure(state="normal" if active else "disabled")
            self.end_session_button.configure(state="disabled")

        self.guided_session_button.configure(state="normal" if active else "disabled")

        sessions = self.session_store.list_sessions(active["id"]) if active else []
        if sessions:
            labels = [self._session_label(s) for s in sessions]
            self.session_selector.configure(values=labels)
            completed = [s for s in sessions if s.get("end_time")]
            self.selected_session = completed[-1] if completed else sessions[-1]
            self.session_selector.set(self._session_label(self.selected_session))
        else:
            self.session_selector.configure(values=["(sin sesiones)"])
            self.session_selector.set("(sin sesiones)")
            self.selected_session = None

        self.session_participant_label.configure(
            text=f"— {participant_label(active)}" if active else ""
        )

        self._refresh_session_view()

    def _refresh_session_view(self):
        self.session_tree.delete(*self.session_tree.get_children())
        active = self.store.get_active()
        if not active or not self.selected_session:
            self.session_stats_label.configure(text="📊  Sin datos para mostrar todavía.")
            return

        combined = read_combined_session_data(active, self.selected_session)
        for row in combined:
            self.session_tree.insert(
                "", "end",
                values=(row["timestamp"].strftime("%H:%M:%S"), row["tipo"], row["valor"]),
            )

        self.session_stats_label.configure(text=self._build_stats_text(combined))

    @staticmethod
    def _build_stats_text(rows: list[dict]) -> str:
        emotions = [r["valor"] for r in rows if r["tipo"] == "Emoción"]
        bpms = []
        for r in rows:
            if r["tipo"] != "BPM":
                continue
            try:
                bpms.append(float(r["valor"]))
            except ValueError:
                continue

        if emotions:
            emotion, freq = Counter(emotions).most_common(1)[0]
            emotion_text = f"{emotion} ({freq}/{len(emotions)} lecturas)"
        else:
            emotion_text = "sin datos"

        bpm_text = f"{sum(bpms) / len(bpms):.1f} BPM  (min {min(bpms):.0f} · max {max(bpms):.0f})" if bpms else "sin datos"

        return f"📊  Emoción más recurrente: {emotion_text}      ·      Promedio BPM: {bpm_text}"


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
