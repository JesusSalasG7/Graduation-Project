"""Renderiza el enunciado completo de un desafio (juego + ubicacion,
enunciado, firma, requisitos y ejemplos) dentro de un frame dado.

Lo comparten la Etapa 1 de la sesion guiada (session_wizard.py) y el boton
"Ver enunciado del desafio" de la pestana Juegos (app.py), para que un
investigador pueda ver exactamente lo mismo que va a ver el participante,
sin duplicar el layout en los dos lugares.
"""

import customtkinter as ctk

FONT_FAMILY = "Segoe UI"


def _section(parent, title: str, font_scale: float = 1.0):
    ctk.CTkLabel(
        parent, text=title,
        font=ctk.CTkFont(family=FONT_FAMILY, size=round(14 * font_scale), weight="bold"),
    ).pack(anchor="w", pady=(0, 6))


def _code_block(parent, text: str, colors: dict, font_scale: float = 1.0):
    card = ctk.CTkFrame(parent, fg_color=colors["BG_CARD_ALT"], corner_radius=8)
    card.pack(anchor="w", fill="x", pady=(0, 18))
    ctk.CTkLabel(
        card, text=text, font=ctk.CTkFont(family="monospace", size=round(12 * font_scale)),
        justify="left", anchor="w",
    ).pack(anchor="w", fill="x", padx=14, pady=10)


def render_statement(parent, game, challenge, colors: dict, wraplength: int = 420, font_scale: float = 1.0):
    """Dibuja, dentro de `parent` (un frame/scrollable frame ya packeable),
    el enunciado completo de `challenge` para `game`. `colors` es el mismo
    dict de paleta que usa el resto de la app/session_wizard.

    `font_scale` multiplica todos los tamanos de letra de este bloque (por
    defecto 1.0, sin cambios) -- la sesion guiada lo usa en 2.0 para que el
    enunciado se lea mas grande que en la vista de la pestana Juegos. El
    ancho de wrapeo tambien crece (a un ritmo mas suave que la letra, para
    no forzar la columna a ser mas ancha que la pantalla) para no perder
    palabras por linea al agrandar la fuente.
    """
    wrap_scale = 1 + (font_scale - 1) * 0.6
    wraplength = round(wraplength * wrap_scale)

    ctk.CTkLabel(
        parent, text=f"🎲  {game.display_name}    ·    📄  {challenge.location}",
        font=ctk.CTkFont(family=FONT_FAMILY, size=round(12 * font_scale)), text_color=colors["TEXT_MUTED"],
    ).pack(anchor="w", pady=(0, 14))

    _section(parent, "📋  Enunciado", font_scale)
    ctk.CTkLabel(
        parent, text=challenge.statement, font=ctk.CTkFont(family=FONT_FAMILY, size=round(14 * font_scale)),
        wraplength=wraplength, justify="left", anchor="w",
    ).pack(anchor="w", fill="x", pady=(0, 18))

    _section(parent, "🧩  Firma exacta a implementar", font_scale)
    _code_block(parent, challenge.signature, colors, font_scale)

    _section(parent, "✅  Requisitos", font_scale)
    for req in challenge.requirements:
        ctk.CTkLabel(
            parent, text=f"•  {req}", font=ctk.CTkFont(family=FONT_FAMILY, size=round(13 * font_scale)),
            wraplength=wraplength - 20, justify="left", anchor="w",
        ).pack(anchor="w", fill="x", pady=(0, 6))
    ctk.CTkLabel(parent, text="", height=8).pack()

    _section(parent, "🧪  Ejemplos y casos de prueba", font_scale)
    _code_block(parent, challenge.examples, colors, font_scale)
