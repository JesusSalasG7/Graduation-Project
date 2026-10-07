"""Renderiza el enunciado completo de un desafío (juego + ubicación,
enunciado, firma, requisitos y ejemplos) dentro de un frame dado.

Lo comparten la Etapa 1 de la sesión guiada (session_wizard.py) y el botón
"Ver enunciado del desafio" de la pestana Juegos (app.py), para que un
investigador pueda ver exactamente lo mismo que va a ver el participante,
sin duplicar el layout en los dos lugares.
"""

import customtkinter as ctk

FONT_FAMILY = "Segoe UI"


def fit_wraplength(parent, labels: list):
    """Ajusta el `wraplength` de `labels` al ancho real de `parent` cada vez
    que este cambia de tamaño. Con un ancho fijo en píxeles el texto se
    cortaba en pantallas más chicas (o con otro escalado de Windows) que la
    de desarrollo, donde la columna es más angosta que ese ancho. `labels`
    es una lista de (label, margen horizontal a descontar, widget vecino en
    la fila o None).

    Se hace en un solo pase diferido para todos los labels: mientras la
    pantalla se acomoda llegan varios <Configure> seguidos, y re-envolver
    cada label en cada uno la dejaba varios segundos trabada."""
    pending = None
    last_width = 0

    def refit():
        nonlocal pending, last_width
        pending = None
        if not parent.winfo_exists() or parent.winfo_width() == last_width:
            return
        last_width = parent.winfo_width()
        for label, margin, beside in labels:
            # winfo_* devuelve píxeles reales; CTk reescala wraplength y los
            # paddings, así que se pasa todo a unidades sin escalar.
            scaling = ctk.ScalingTracker.get_widget_scaling(label)
            available = last_width / scaling - margin - 8
            if beside is not None:
                available -= beside.winfo_reqwidth() / scaling
            available = max(round(available), 100)
            if available != label.cget("wraplength"):
                label.configure(wraplength=available)

    def schedule(_event):
        nonlocal pending
        if pending is not None:
            parent.after_cancel(pending)
        pending = parent.after(40, refit)

    parent.bind("<Configure>", schedule, add="+")


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

    `font_scale` multiplica todos los tamaños de letra de este bloque (por
    defecto 1.0, sin cambios) -- la sesión guiada lo usa en 2.0 para que el
    enunciado se lea más grande que en la vista de la pestana Juegos. El
    ancho de wrapeo también crece (a un ritmo más suave que la letra, para
    no forzar la columna a ser más ancha que la pantalla) para no perder
    palabras por línea al agrandar la fuente.
    """
    wrap_scale = 1 + (font_scale - 1) * 0.6
    wraplength = round(wraplength * wrap_scale)

    location_label = ctk.CTkLabel(
        parent, text=f"🎲  {game.display_name}    ·    📄  {challenge.location}",
        font=ctk.CTkFont(family=FONT_FAMILY, size=round(12 * font_scale)), text_color=colors["TEXT_MUTED"],
        justify="left",
    )
    location_label.pack(anchor="w", pady=(0, 14))
    fitted_labels = [(location_label, 0, None)]

    _section(parent, "📋  Enunciado", font_scale)
    statement_label = ctk.CTkLabel(
        parent, text=challenge.statement, font=ctk.CTkFont(family=FONT_FAMILY, size=round(14 * font_scale)),
        wraplength=wraplength, justify="left", anchor="w",
    )
    statement_label.pack(anchor="w", fill="x", pady=(0, 18))
    fitted_labels.append((statement_label, 0, None))

    _section(parent, "🧩  Firma exacta a implementar", font_scale)
    _code_block(parent, challenge.signature, colors, font_scale)

    _section(parent, "✅  Requisitos", font_scale)
    for req in challenge.requirements:
        req_label = ctk.CTkLabel(
            parent, text=f"•  {req}", font=ctk.CTkFont(family=FONT_FAMILY, size=round(13 * font_scale)),
            wraplength=wraplength - 20, justify="left", anchor="w",
        )
        req_label.pack(anchor="w", fill="x", pady=(0, 6))
        fitted_labels.append((req_label, 0, None))
    ctk.CTkLabel(parent, text="", height=8).pack()

    _section(parent, "🧪  Ejemplos y casos de prueba", font_scale)
    _code_block(parent, challenge.examples, colors, font_scale)

    fit_wraplength(parent, fitted_labels)
