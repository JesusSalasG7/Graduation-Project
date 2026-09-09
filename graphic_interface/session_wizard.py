"""Modulo de "sesion guiada": reemplaza toda la interfaz por un asistente de
4 etapas para el participante activo, empezando por el juego mas facil.

Etapa 1 -- pantalla dividida: enunciado completo del desafio a la izquierda,
           7 preguntas de opcion multiple sobre ESE enunciado a la derecha
           (banco estatico, ver statement_quiz.py).
Etapa 2 -- el participante escribe su propio prompt para resolverlo; al
           enviarlo, ese prompt -- y SOLO ese prompt, sin el enunciado ni
           ningun otro contexto -- se envia a una IA completamente aislada
           (ver isolated_prompt.py y challenge_solver.generate_isolated_
           response): si el prompt no alcanza a describir el problema, la
           respuesta lo va a reflejar.
Etapa 3 -- pantalla dividida: la respuesta cruda que devolvio esa IA
           aislada a la izquierda, 7 preguntas de opcion multiple sobre esa
           respuesta concreta a la derecha (generadas dinamicamente).
Etapa 4 -- razonamiento: 7 preguntas de opcion multiple sobre por que esa
           respuesta es (o no es) valida frente al enunciado (generadas
           junto con las de la Etapa 3).

Las respuestas de los 3 cuestionarios se guardan por participante (ver
quiz_results.py) sin bloquear el avance -- son un registro, no un examen
con nota de corte.

Al terminar un desafio se puede pasar al siguiente (en orden de
dificultad), o guardar el progreso y salir: la proxima vez que este
participante entre a la sesion guiada, retoma en el desafio siguiente
en lugar de volver a empezar desde el primero.
"""

import threading
from tkinter import messagebox

import customtkinter as ctk

from challenge_solver import GUIDED_SESSION_GAME_ORDER, ChallengeSolveResult, generate_isolated_response
from challenges import get_challenge
from game_launcher import discover_games
from participant_store import participant_label
from personal_records import load_personal_record
from quiz import QuizQuestion
from quiz_results import save_quiz_answers
from statement_view import render_statement
from statement_quiz import get_statement_questions

FONT_FAMILY = "Segoe UI"
PROGRESS_ATTRIBUTE = "sesion_guiada_siguiente_juego"

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
            command=self.app.exit_session_wizard,
        ).place(relx=1.0, rely=0.0, anchor="ne", x=-20, y=18)

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
        title: str, wraplength: int = 380,
    ):
        answers.clear()
        self._section(parent, title)
        wraplength = wrap(wraplength)
        if not questions:
            ctk.CTkLabel(
                parent, text="No se generaron preguntas para este caso.",
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

    # ---------------- flujo ----------------
    def start(self):
        participant = self.app.store.get_active()
        saved_index = 0
        if participant:
            saved_index = participant.get("attributes", {}).get(PROGRESS_ATTRIBUTE, 0)
        if not isinstance(saved_index, int) or not (0 <= saved_index < len(GUIDED_SESSION_GAME_ORDER)):
            saved_index = 0
        self.game_index = saved_index
        self._show_welcome()

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
                "desafío tiene 4 etapas:\n\n"
                "Etapa 1: Leer el enunciado y responder 7 preguntas sobre él.\n"
                "Etapa 2: Escribir tu prompt para resolverlo.\n"
                "Etapa 3: Ver el resultado y responder 7 preguntas sobre la solución.\n"
                "Etapa 4: Responder 7 preguntas de razonamiento sobre esa solución."
            )
        else:
            intro_text = (
                "Vas a resolver una serie de desafíos de programación, del más\n"
                "fácil al más difícil, escribiendo tu propio prompt para pedirle\n"
                "a una IA que lo resuelva. Cada desafío tiene 4 etapas:\n\n"
                "Etapa 1: Leer el enunciado y responder 7 preguntas sobre él.\n"
                "Etapa 2: Escribir tu prompt para resolverlo.\n"
                "Etapa 3: Ver el resultado y responder 7 preguntas sobre la solución.\n"
                "Etapa 4: Responder 7 preguntas de razonamiento sobre esa solución.\n\n"
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
        if self.current_game is None or self.current_challenge is None:
            self._advance_or_finish()
            return
        self._show_stage1()

    # ---------------- Etapa 1 ----------------
    def _show_stage1(self):
        self._clear()
        challenge = self.current_challenge
        game = self.current_game

        self._header(self.container, "ETAPA 1 DE 4 · EL PROBLEMA", challenge.title)
        self._exit_button(self.container)

        left, right, buttons_row = self._split_columns(self.container)

        render_statement(left, game, challenge, self.c, wraplength=420, font_scale=2.0)

        self._build_quiz(
            right, get_statement_questions(game.name), self.stage1_answers,
            title="📝  Preguntas sobre el enunciado",
        )

        def on_continue():
            self._save_answers("etapa1_enunciado", get_statement_questions(game.name), self.stage1_answers)
            self._show_stage2()

        ctk.CTkButton(
            buttons_row, text="Ya entendí el problema · Escribir mi prompt  ▶", height=scaled(42), corner_radius=10,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(13), weight="bold"),
            fg_color=self.c["ACCENT"], hover_color=self.c["ACCENT_HOVER"],
            command=on_continue,
        ).pack(fill="x")

    # ---------------- Etapa 2 ----------------
    def _show_stage2(self):
        self._clear()
        challenge = self.current_challenge

        self._header(self.container, "ETAPA 2 DE 4 · TU PROMPT", "Escribe el prompt para resolverlo")
        self._exit_button(self.container)

        body = ctk.CTkFrame(self.container, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=36, pady=(10, 20))

        ctk.CTkLabel(
            body,
            text=(
                "Escribe, en tus propias palabras, el prompt que le darías a una IA "
                "para que resuelva este ejercicio. Abajo tenés, como referencia, la "
                "función exacta que hay que implementar (no hace falta que la "
                "memorices, ni es lo que se evalúa). Importante: la IA que va a "
                "responder NO va a ver el enunciado ni nada de lo que leíste antes -- "
                "solo el texto exacto que escribas acá. Si tu prompt no incluye el "
                "contexto necesario, la respuesta lo va a reflejar."
            ),
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12)), text_color=self.c["TEXT_MUTED"],
            wraplength=wrap(900), justify="left",
        ).pack(anchor="w", pady=(0, 10))

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
            prompt_box.configure(state="disabled")
            send_button.configure(state="disabled", text="Generando respuesta...")
            status_label.configure(
                text="🤖  Generando una respuesta aislada y preparando las preguntas "
                     "(puede tardar uno o dos minutos)...",
                text_color=self.c["TEXT_MUTED"],
            )
            threading.Thread(target=self._run_isolated_prompt, args=(text,), daemon=True).start()

        send_button.configure(command=on_send)

    def _run_isolated_prompt(self, participant_prompt: str):
        try:
            result = generate_isolated_response(self.current_challenge, participant_prompt)
        except Exception as exc:  # el hilo de fondo no debe tumbar la app
            result = ChallengeSolveResult(ok=False, error=str(exc))
        self.app.after(0, lambda: self._show_stage3(result))

    # ---------------- Etapa 3 ----------------
    def _show_stage3(self, result: ChallengeSolveResult):
        self._clear()
        self.current_result = result
        challenge = self.current_challenge

        self._header(self.container, "ETAPA 3 DE 4 · RESULTADO", challenge.title)
        self._exit_button(self.container)

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
            text="Recordá: esta IA solo vio el prompt exacto que escribiste en la Etapa 2, "
            "nada más.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(11)), text_color=self.c["TEXT_MUTED"],
            wraplength=wrap(420), justify="left",
        ).pack(anchor="w", pady=(0, 8))
        self._code_block(left, result.response_text or "(sin respuesta para mostrar)")

        self._build_quiz(
            right, result.comprehension_questions, self.stage3_answers,
            title="📝  Preguntas sobre la respuesta",
        )

        def on_retry():
            self._show_stage2()

        def on_continue():
            self._save_answers("etapa3_comprension", result.comprehension_questions, self.stage3_answers)
            self._show_stage4()

        ctk.CTkButton(
            buttons_row, text="🔁  Reintentar este desafío", height=scaled(42), corner_radius=10,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(13)),
            fg_color=self.c["BG_CARD_ALT"], hover_color=self.c["BORDER"],
            command=on_retry,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            buttons_row, text="Continuar a Etapa 4 · Razonamiento  ▶", height=scaled(42), corner_radius=10,
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(13), weight="bold"),
            fg_color=self.c["ACCENT"], hover_color=self.c["ACCENT_HOVER"],
            command=on_continue,
        ).pack(side="left")

    # ---------------- Etapa 4 ----------------
    def _show_stage4(self):
        self._clear()
        result = self.current_result
        challenge = self.current_challenge
        is_last = self.game_index >= len(GUIDED_SESSION_GAME_ORDER) - 1

        self._header(self.container, "ETAPA 4 DE 4 · RAZONAMIENTO", challenge.title)
        self._exit_button(self.container)

        body = ctk.CTkFrame(self.container, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=36, pady=(10, 20))
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(body, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")

        ctk.CTkLabel(
            scroll,
            text="Repasá la respuesta y respondé sobre por qué es (o no es) una respuesta "
                 "válida al enunciado, dado que la IA no lo vio.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(12)), text_color=self.c["TEXT_MUTED"],
            wraplength=wrap(880), justify="left",
        ).pack(anchor="w", pady=(0, 14))

        self._section(scroll, "💻  Código generado (referencia)")
        self._code_block(scroll, result.response_text if result else "(sin respuesta para mostrar)")

        self._build_quiz(
            scroll, result.reasoning_questions if result else [], self.stage4_answers,
            title="🧠  Preguntas de razonamiento", wraplength=820,
        )

        buttons_row = ctk.CTkFrame(body, fg_color="transparent")
        buttons_row.grid(row=1, column=0, sticky="ew", pady=(14, 0))

        def on_retry():
            self._show_stage2()

        def on_next():
            self._save_answers(
                "etapa4_razonamiento",
                result.reasoning_questions if result else [], self.stage4_answers,
            )
            self._advance_or_finish()

        def on_save_progress():
            self._save_answers(
                "etapa4_razonamiento",
                result.reasoning_questions if result else [], self.stage4_answers,
            )
            self._save_progress(self.game_index + 1)
            messagebox.showinfo(
                "Progreso guardado",
                "Guardamos tu progreso. La próxima vez que entres a la sesión\n"
                "guiada vas a retomar en el siguiente desafío.",
                parent=self.app,
            )
            self.app.exit_session_wizard()

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
                command=on_next,
            ).pack(side="left")
        else:
            ctk.CTkButton(
                buttons_row, text="Siguiente juego  ▶", height=scaled(42), corner_radius=10,
                font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(13), weight="bold"),
                fg_color=self.c["ACCENT"], hover_color=self.c["ACCENT_HOVER"],
                command=on_next,
            ).pack(side="left", padx=(0, 8))
            ctk.CTkButton(
                buttons_row, text="💾  Guardar progreso y salir", height=scaled(42), corner_radius=10,
                font=ctk.CTkFont(family=FONT_FAMILY, size=scaled(13)),
                fg_color=self.c["BG_CARD_ALT"], hover_color=self.c["BORDER"],
                command=on_save_progress,
            ).pack(side="left")

    def _advance_or_finish(self):
        self.game_index += 1
        if self.game_index >= len(GUIDED_SESSION_GAME_ORDER):
            self._clear_progress()
            self.app.exit_session_wizard()
            return
        self._start_current_game()
