"""Pestaña "Análisis": features EEG de carga cognitiva (EEG1, EEG2) por
etapa, leídas del dataset consolidado. Solo muestra lo que calcula
analisis/ (ver analisis/README.md); no hace cálculos propios.

Recibe la paleta y la tipografía desde ui/app.py (igual que SessionWizard
recibe sus colores) para no duplicar las constantes del panel.
"""

import threading
import tkinter.messagebox as messagebox
from tkinter import ttk
from typing import Callable, Optional

import customtkinter as ctk
import numpy as np
import pandas as pd

from analisis.config import BASELINE_STAGE, DATASET_FILE, AnalysisConfig
from analisis.loader import compute_features, export_features
from analisis.report import STAGE_NAMES, filter_participant, quality_summary, stage_summary

# matplotlib se usa solo para el gráfico de barras; si faltara, la pestaña
# sigue funcionando sin él (con un aviso en su lugar).
try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
except ImportError:  # pragma: no cover
    FigureCanvasTkAgg = None
    Figure = None

ALL_PARTICIPANTS = "Todos"

EFFORT_NOTE = (
    "EEG1 = θ/(α+β) y EEG2 = θ/α miden esfuerzo mental y carga de memoria de "
    "trabajo, NO comprensión. Sus valores solo son comparables dentro del mismo "
    "participante, o entre participantes después de normalizar (cambio % contra "
    f"la Etapa {BASELINE_STAGE} del mismo desafío, z-score o Min-Max)."
)

# (columna de la tabla de features, encabezado, ancho, formato)
TABLE_COLUMNS = [
    ("Participante_ID", "Part.", 60, "{:.0f}"),
    ("Desafio", "Desafío", 70, "{:.0f}"),
    ("Etapa", "Etapa", 60, "{:.0f}"),
    ("Intento", "Intento", 70, "{:.0f}"),
    ("Muestras_Validas", "Válidas", 75, "{:.0f}"),
    ("Pct_Descartado", "% desc.", 75, "{:.1f}"),
    ("EEG1_Media", "EEG1", 75, "{:.4f}"),
    ("EEG1_Media_Cambio_Pct", "EEG1 Δ%", 80, "{:+.2f}"),
    ("EEG2_Media", "EEG2", 75, "{:.4f}"),
    ("EEG2_Media_Cambio_Pct", "EEG2 Δ%", 80, "{:+.2f}"),
    ("AlphaTheta_Media", "α/θ", 75, "{:.4f}"),
    ("Theta_Mediana", "θ med.", 75, "{:.3f}"),
    ("Delta_Media", "δ media", 75, "{:.3f}"),
    ("eSense_Attention_Media", "Atención*", 85, "{:.1f}"),
    ("eSense_Meditation_Media", "Meditación*", 95, "{:.1f}"),
]

EEG1_COLOR = "#5865f2"
EEG2_COLOR = "#3fb8af"


def _fmt(value, pattern: str) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)) or pd.isna(value):
        return "—"
    try:
        return pattern.format(float(value))
    except (TypeError, ValueError):
        return str(value)


class AnalysisView:
    def __init__(self, parent: ctk.CTkFrame, colors: dict, font_family: str, scaled: Callable[[int], int]):
        self.parent = parent
        self.c = colors
        self.font_family = font_family
        self.scaled = scaled
        self.cfg = AnalysisConfig()
        self.features: Optional[pd.DataFrame] = None
        self.warnings: list[str] = []
        self._loading = False
        self._canvas = None
        self._build()

    # ---------------- Construcción ----------------
    def _font(self, size: int, bold: bool = False) -> ctk.CTkFont:
        return ctk.CTkFont(family=self.font_family, size=self.scaled(size), weight="bold" if bold else "normal")

    def _card(self, parent, title: str) -> ctk.CTkFrame:
        card = ctk.CTkFrame(parent, fg_color=self.c["BG_CARD"], corner_radius=12)
        card.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(card, text=title, font=self._font(13, bold=True)).pack(anchor="w", padx=18, pady=(16, 6))
        return card

    def _build(self):
        wrapper = ctk.CTkScrollableFrame(self.parent, fg_color="transparent")
        wrapper.pack(fill="both", expand=True, padx=26, pady=(24, 20))

        ctk.CTkLabel(wrapper, text="Análisis EEG", font=self._font(22, bold=True)).pack(anchor="w")
        ctk.CTkLabel(
            wrapper,
            text="Features de carga cognitiva (EEG1, EEG2) por etapa, calculadas desde el dataset consolidado.",
            font=self._font(12), text_color=self.c["TEXT_MUTED"],
        ).pack(anchor="w", pady=(2, 14))

        # Controles
        controls = ctk.CTkFrame(wrapper, fg_color=self.c["BG_CARD"], corner_radius=12)
        controls.pack(fill="x", pady=(0, 14))
        row = ctk.CTkFrame(controls, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=16)
        ctk.CTkLabel(row, text="Participante", font=self._font(12)).pack(side="left", padx=(0, 8))
        self.participant_var = ctk.StringVar(value=ALL_PARTICIPANTS)
        self.participant_menu = ctk.CTkOptionMenu(
            row, variable=self.participant_var, values=[ALL_PARTICIPANTS], width=self.scaled(150),
            font=self._font(12), fg_color=self.c["BG_CARD_ALT"], button_color=self.c["ACCENT"],
            button_hover_color=self.c["ACCENT_HOVER"], command=lambda _: self._render(),
        )
        self.participant_menu.pack(side="left", padx=(0, 14))
        ctk.CTkButton(
            row, text="🔄  Recalcular", height=self.scaled(32), corner_radius=8, font=self._font(12, bold=True),
            fg_color=self.c["ACCENT"], hover_color=self.c["ACCENT_HOVER"], command=self.refresh,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            row, text="💾  Exportar CSV", height=self.scaled(32), corner_radius=8, font=self._font(12),
            fg_color=self.c["BG_CARD_ALT"], hover_color=self.c["BORDER"], command=self._export,
        ).pack(side="left")
        self.status_label = ctk.CTkLabel(
            controls, text=f"Fuente: {DATASET_FILE}", font=self._font(11), text_color=self.c["TEXT_MUTED"],
            anchor="w", justify="left",
        )
        self.status_label.pack(fill="x", padx=18, pady=(0, 14))

        # Nota de interpretación
        note = self._card(wrapper, "ℹ️  Cómo leer estos valores")
        ctk.CTkLabel(
            note, text=EFFORT_NOTE, font=self._font(11), text_color=self.c["TEXT_MUTED"],
            wraplength=self.scaled(700), justify="left", anchor="w",
        ).pack(fill="x", padx=18, pady=(0, 16))

        # Calidad
        quality = self._card(wrapper, "🩺  Calidad de la señal")
        self.quality_label = ctk.CTkLabel(
            quality, text="", font=self._font(11), wraplength=self.scaled(700), justify="left", anchor="w",
        )
        self.quality_label.pack(fill="x", padx=18, pady=(0, 16))

        # Gráfico
        chart = self._card(wrapper, "📊  EEG1 y EEG2 por etapa")
        self.chart_caption = ctk.CTkLabel(
            chart, text="", font=self._font(11), text_color=self.c["TEXT_MUTED"],
            wraplength=self.scaled(700), justify="left", anchor="w",
        )
        self.chart_caption.pack(fill="x", padx=18, pady=(0, 6))
        self.chart_holder = ctk.CTkFrame(chart, fg_color=self.c["BG_CARD"])
        self.chart_holder.pack(fill="x", padx=18, pady=(0, 16))

        # Tabla
        table = self._card(wrapper, "🧾  Features por etapa")
        ctk.CTkLabel(
            table,
            text="Δ% = cambio contra la línea base. * eSense: métricas propietarias de NeuroSky. "
                 "Las filas en naranja tienen datos insuficientes y las rojas, δ atípicamente alta. "
                 "El CSV exportado trae todas las columnas (DE, mín., máx., z-score, Min-Max…).",
            font=self._font(11), text_color=self.c["TEXT_MUTED"], wraplength=self.scaled(700),
            justify="left", anchor="w",
        ).pack(fill="x", padx=18, pady=(0, 8))
        table_frame = ctk.CTkFrame(table, fg_color="transparent")
        table_frame.pack(fill="x", padx=18, pady=(0, 16))
        table_frame.grid_columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            table_frame, columns=[col for col, *_ in TABLE_COLUMNS], show="headings", height=12,
        )
        for col, label, width, _ in TABLE_COLUMNS:
            self.tree.heading(col, text=label, anchor="center")
            self.tree.column(col, width=self.scaled(width), anchor="center", stretch=False)
        self.tree.tag_configure("insuficiente", foreground=self.c["WARNING"])
        self.tree.tag_configure("delta", foreground=self.c["DANGER"])
        self.tree.grid(row=0, column=0, sticky="ew")
        y_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        x_scroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")

    # ---------------- Datos ----------------
    def refresh(self):
        """Recalcula desde el CSV en un hilo aparte (lee y procesa todas las
        listas crudas, puede tardar unos segundos)."""
        if self._loading:
            return
        self._loading = True
        self.status_label.configure(text="Calculando features…")

        def work():
            try:
                features, warnings = compute_features(DATASET_FILE, self.cfg)
                error = None
            except Exception as exc:  # se muestra en la pestaña, la app sigue
                features, warnings, error = None, [], exc
            self.parent.after(0, lambda: self._on_loaded(features, warnings, error))

        threading.Thread(target=work, daemon=True).start()

    def refresh_if_needed(self):
        if self.features is None:
            self.refresh()

    def _on_loaded(self, features, warnings, error):
        self._loading = False
        if error is not None:
            self.status_label.configure(text=f"⚠️  {error}")
            return
        self.features, self.warnings = features, warnings
        participants = sorted(int(p) for p in features["Participante_ID"].dropna().unique()) if not features.empty else []
        options = [ALL_PARTICIPANTS] + [f"Participante {p}" for p in participants]
        self.participant_menu.configure(values=options)
        if self.participant_var.get() not in options:
            self.participant_var.set(ALL_PARTICIPANTS)
        self.status_label.configure(
            text=f"Fuente: {DATASET_FILE} · {len(features)} filas · {len(participants)} participantes"
        )
        self._render()

    def _selected_participant(self) -> Optional[int]:
        value = self.participant_var.get()
        return None if value == ALL_PARTICIPANTS else int(value.split()[-1])

    def _export(self):
        if self.features is None or self.features.empty:
            messagebox.showinfo("Exportar CSV", "Todavía no hay features calculadas.")
            return
        path = export_features(self.features)
        messagebox.showinfo("Exportar CSV", f"Tabla de features guardada en:\n{path}")

    # ---------------- Render ----------------
    def _render(self):
        if self.features is None:
            return
        selected = filter_participant(self.features, self._selected_participant())
        self._render_quality(selected)
        self._render_chart(selected)
        self._render_table(selected)

    def _render_quality(self, df: pd.DataFrame):
        q = quality_summary(df)
        lines = []
        if q["pct_descartado_por_etapa"]:
            pct = " · ".join(f"Etapa {stage}: {value}%" for stage, value in q["pct_descartado_por_etapa"].items())
            lines.append(f"Muestras descartadas (PoorSignal > {self.cfg.poor_signal_threshold}), promedio por etapa: {pct}")
        lines.append(
            f"Datos insuficientes (< {self.cfg.min_valid_samples} muestras o < "
            f"{self.cfg.min_valid_fraction:.0%} válidas): "
            + (", ".join(q["insuficientes"]) if q["insuficientes"] else "ninguna etapa")
        )
        lines.append(
            f"⚠️ δ atípicamente alta (z > {self.cfg.delta_alert_z}; posibles parpadeos o artefactos, Fp1): "
            + (", ".join(q["delta_alta"]) if q["delta_alta"] else "ninguna")
        )
        if q["filas"] and q["con_linea_base"] == 0:
            lines.append(f"⚠️ Sin línea base (Etapa {self.cfg.baseline_stage}): no se calculó el cambio %.")
        elif q["filas"] - q["con_linea_base"] > 0:
            lines.append(f"Filas sin línea base válida: {q['filas'] - q['con_linea_base']} de {q['filas']}.")
        self.quality_label.configure(text="\n".join(lines))

    def _render_chart(self, df: pd.DataFrame):
        for child in self.chart_holder.winfo_children():
            child.destroy()
        self._canvas = None
        if Figure is None:
            self.chart_caption.configure(text="matplotlib no está instalado: el gráfico no está disponible.")
            return
        summary = stage_summary(df)
        if summary.empty:
            self.chart_caption.configure(text="No hay etapas con datos suficientes para graficar.")
            return

        use_change = summary[["EEG1_Media_Cambio_Pct", "EEG2_Media_Cambio_Pct"]].notna().any().any()
        if use_change:
            cols = ("EEG1_Media_Cambio_Pct", "EEG2_Media_Cambio_Pct")
            ylabel = f"Cambio % vs. Etapa {self.cfg.baseline_stage}"
            self.chart_caption.configure(
                text=f"Barras: cambio % medio contra la línea base (Etapa {self.cfg.baseline_stage} del mismo "
                     "desafío, por eso vale 0). Encima: el valor medio de EEG1 / EEG2. n = filas promediadas."
            )
        else:
            cols = ("EEG1_Media", "EEG2_Media")
            ylabel = "Valor medio (log)"
            self.chart_caption.configure(
                text="⚠️ Sin línea base: se grafican los valores medios sin normalizar, comparables solo "
                     "dentro del mismo participante."
            )

        bg, fg, muted = self.c["BG_CARD"], "#e6e8f0", self.c["TEXT_MUTED"]
        fig = Figure(figsize=(8, 3.4), dpi=100, facecolor=bg)
        ax = fig.add_subplot(111)
        ax.set_facecolor(bg)
        x = np.arange(len(summary))
        width = 0.36
        for offset, col, raw_col, color, label in (
            (-width / 2, cols[0], "EEG1_Media", EEG1_COLOR, "EEG1 = θ/(α+β)"),
            (width / 2, cols[1], "EEG2_Media", EEG2_COLOR, "EEG2 = θ/α"),
        ):
            values = summary[col].fillna(0).to_numpy()
            bars = ax.bar(x + offset, values, width, color=color, label=label)
            if use_change:
                for bar, raw in zip(bars, summary[raw_col]):
                    height = bar.get_height()
                    ax.annotate(
                        f"{raw:.3f}", (bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3 if height >= 0 else -11), textcoords="offset points",
                        ha="center", fontsize=8, color=muted,
                    )
        ax.axhline(0, color=muted, linewidth=0.8)
        ax.set_xticks(x)
        ax.set_xticklabels(
            [f"Etapa {int(s)}\n{STAGE_NAMES.get(int(s), '')}\nn={int(n)}" for s, n in zip(summary["Etapa"], summary["Filas"])],
            color=fg, fontsize=9,
        )
        ax.set_ylabel(ylabel, color=fg, fontsize=9)
        ax.tick_params(axis="y", colors=muted, labelsize=8)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
        for spine in ("left", "bottom"):
            ax.spines[spine].set_color(self.c["BORDER"])
        ax.margins(y=0.2)
        ax.legend(frameon=False, labelcolor=fg, fontsize=9, loc="upper right")
        fig.tight_layout()

        self._canvas = FigureCanvasTkAgg(fig, master=self.chart_holder)
        self._canvas.draw()
        self._canvas.get_tk_widget().pack(fill="x")

    def _render_table(self, df: pd.DataFrame):
        self.tree.delete(*self.tree.get_children())
        for _, row in df.iterrows():
            tags = ()
            if bool(row.get("Datos_Insuficientes")):
                tags = ("insuficiente",)
            elif bool(row.get("Delta_Atipica")):
                tags = ("delta",)
            self.tree.insert(
                "", "end", values=[_fmt(row.get(col), pattern) for col, _, _, pattern in TABLE_COLUMNS], tags=tags,
            )
