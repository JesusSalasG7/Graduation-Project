"""GUI principal: lanzador de juegos + gestion de participantes."""

import threading
import tkinter.messagebox as messagebox
from pathlib import Path
from tkinter import ttk

import customtkinter as ctk

from game_launcher import (
    PROJECT_ROOT,
    discover_games,
    open_in_vscode,
    play_game,
    repair_environment,
    start_emotion_tracker,
)
from participant_store import ParticipantStore

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_FILE = DATA_DIR / "participants.json"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Paleta de la app (tema oscuro fijo)
BG_APP = "#15171d"
BG_SIDEBAR = "#101217"
BG_CARD = "#1e212a"
BG_CARD_ALT = "#252834"
BORDER = "#2c303c"
TEXT_MUTED = "#8b8fa3"

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


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Panel de Experimento")
        self.geometry("1080x680")
        self.minsize(920, 580)
        self.configure(fg_color=BG_APP)

        self.store = ParticipantStore(DATA_FILE)
        self.emotion_process = None
        self.emotion_participant_id = None

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
        for frame in (self.tab_games, self.tab_participants):
            frame.grid(row=0, column=0, sticky="nsew")

        self._build_games_tab()
        self._build_participants_tab()
        self._select_nav("games")

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
        frames = {"games": self.tab_games, "participants": self.tab_participants}
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

        ctk.CTkButton(
            actions, text="🔄  Actualizar", width=130, height=34, corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=BG_CARD_ALT, hover_color=BORDER, text_color="white",
            command=self._refresh_games,
        ).pack(side="left")

        self.games_scroll = ctk.CTkScrollableFrame(self.tab_games, fg_color="transparent")
        self.games_scroll.pack(fill="both", expand=True, padx=20, pady=10)

        self._refresh_games()

    def _refresh_games(self):
        for child in self.games_scroll.winfo_children():
            child.destroy()

        games = discover_games()
        if not games:
            ctk.CTkLabel(
                self.games_scroll, text="No se encontraron carpetas Game-*.", text_color=TEXT_MUTED
            ).pack(pady=20)
            return

        for game in games:
            card = ctk.CTkFrame(self.games_scroll, fg_color=BG_CARD, corner_radius=12)
            card.pack(fill="x", pady=6, padx=4)
            card.grid_columnconfigure(0, weight=1)

            info = ctk.CTkFrame(card, fg_color="transparent")
            info.grid(row=0, column=0, sticky="w", padx=18, pady=14)

            title_row = ctk.CTkFrame(info, fg_color="transparent")
            title_row.pack(anchor="w")
            ctk.CTkLabel(
                title_row, text=f"🎲  {game.name}", font=ctk.CTkFont(family=FONT_FAMILY, size=15, weight="bold")
            ).pack(side="left")
            if game.display_name and game.display_name != game.name:
                ctk.CTkLabel(
                    title_row, text=f"   ·   {game.display_name}",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=13), text_color=TEXT_MUTED,
                ).pack(side="left")

            if game.is_playable:
                pill_text, pill_bg, pill_fg = "● Listo para jugar", "#1c3a26", "#4ade80"
            else:
                pill_text, pill_bg, pill_fg = "● Sin main.py", "#332a1c", "#c9a15a"
            ctk.CTkLabel(
                info, text=pill_text, font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
                fg_color=pill_bg, text_color=pill_fg, corner_radius=10, padx=10, pady=2,
            ).pack(anchor="w", pady=(6, 0))

            buttons = ctk.CTkFrame(card, fg_color="transparent")
            buttons.grid(row=0, column=1, sticky="e", padx=18, pady=14)

            ctk.CTkButton(
                buttons, text="📝  VS Code", width=130, height=34, corner_radius=8,
                font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                fg_color=BG_CARD_ALT, hover_color=BORDER, text_color="white",
                command=lambda g=game: self._open_vscode(g),
            ).pack(side="left", padx=(0, 8))

            play_btn = ctk.CTkButton(
                buttons, text="▶  Jugar", width=110, height=34, corner_radius=8,
                font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
                fg_color=SUCCESS, hover_color=SUCCESS_HOVER,
                command=lambda g=game: self._play(g),
            )
            play_btn.pack(side="left")
            if not game.is_playable:
                play_btn.configure(state="disabled", fg_color=BG_CARD_ALT, text_color=TEXT_MUTED)

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
            f"🎥  Seguimiento: activo\n{participant['nombre']} {participant['apellido']} · {session_label}",
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
            return f"👤 Participante activo: {active['nombre']} {active['apellido']} (C.I. {active['cedula']})"
        return "👤 Participante activo: ninguno"

    def _build_participants_tab(self):
        wrapper = ctk.CTkFrame(self.tab_participants, fg_color="transparent")
        wrapper.pack(fill="both", expand=True, padx=26, pady=(24, 20))

        ctk.CTkLabel(
            wrapper, text="Participantes", font=ctk.CTkFont(family=FONT_FAMILY, size=22, weight="bold")
        ).pack(anchor="w")
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
        ).pack(anchor="w", padx=18, pady=(18, 12))

        self.entry_nombre = self._labeled_entry(form, "Nombre")
        self.entry_apellido = self._labeled_entry(form, "Apellido")
        self.entry_cedula = self._labeled_entry(form, "Cedula")

        ctk.CTkButton(
            form, text="💾  Guardar participante", height=36, corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._save_participant,
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

        columns = ("nombre", "apellido", "cedula", "fecha")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        for col, label, width in (
            ("nombre", "Nombre", 150),
            ("apellido", "Apellido", 150),
            ("cedula", "Cedula", 130),
            ("fecha", "Registrado", 170),
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

    def _labeled_entry(self, parent, label_text):
        ctk.CTkLabel(
            parent, text=label_text, font=ctk.CTkFont(family=FONT_FAMILY, size=12), text_color=TEXT_MUTED
        ).pack(anchor="w", padx=18)
        entry = ctk.CTkEntry(
            parent, width=230, height=34, corner_radius=8, fg_color=BG_CARD_ALT, border_width=0,
        )
        entry.pack(padx=18, pady=(2, 12))
        return entry

    def _refresh_participants(self):
        self.tree.delete(*self.tree.get_children())
        for p in self.store.list_participants():
            self.tree.insert("", "end", iid=p["id"], values=(p["nombre"], p["apellido"], p["cedula"], p["created_at"]))
        self.active_label.configure(text=self._active_label_text())
        self.participants_active_label.configure(text=self._active_label_text())

    def _save_participant(self):
        nombre = self.entry_nombre.get().strip()
        apellido = self.entry_apellido.get().strip()
        cedula = self.entry_cedula.get().strip()
        if not nombre or not apellido or not cedula:
            messagebox.showwarning("Datos incompletos", "Nombre, apellido y cedula son obligatorios.")
            return
        try:
            self.store.add_participant(nombre, apellido, cedula)
        except ValueError as exc:
            messagebox.showerror("Cedula duplicada", str(exc))
            return
        self.entry_nombre.delete(0, "end")
        self.entry_apellido.delete(0, "end")
        self.entry_cedula.delete(0, "end")
        self._refresh_participants()

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

    def _delete_selected(self):
        pid = self._selected_id()
        if not pid:
            messagebox.showinfo("Sin seleccion", "Selecciona un participante de la tabla primero.")
            return
        if messagebox.askyesno("Confirmar", "Eliminar este participante?"):
            self.store.delete_participant(pid)
            self._refresh_participants()


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
