"""Pestaña "Análisis": EEG1 (Alfa/Theta) y EEG2 (Theta) normalizados por
participante, por etapa, y su relación con la comprensión. Solo muestra lo
que calcula analisis/ (ver analisis/README.md); no hace cálculos propios.

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

from analisis.config import RUTA_DATASET, RUTA_SALIDA, ConfigAnalisis
from analisis.estadistica import NOTA_MUESTRA_PEQUENA
from analisis.loader import ResultadoAnalisis, ejecutar_analisis, exportar
from analisis.pipeline import interpretar_carga
from analisis.por_desafio import desafios_disponibles, vista_desafio

# matplotlib se usa para embeber los gráficos; si faltara, la pestaña
# sigue funcionando con las tablas (con un aviso en lugar del gráfico).
try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
except ImportError:  # pragma: no cover
    FigureCanvasTkAgg = None

ALL_PARTICIPANTS = "Todos"
ALL_CHALLENGES = "Todos juntos"

INTERPRETACION = (
    "• Los valores son z dentro de cada participante: z = 0 es su nivel habitual. Son relativos a "
    "cada persona, nunca absolutos.\n"
    "• EEG1 = Alfa/Theta. EEG1_z bajo (negativo) = mayor carga cognitiva; alto = menor carga o más relajación.\n"
    "• EEG2 = Theta. EEG2_z alto (positivo) = mayor carga de memoria de trabajo o esfuerzo; bajo = menor demanda.\n"
    "• Patrón de alta carga: EEG1_z bajo y EEG2_z alto a la vez. Si se contradicen, el resultado es "
    "no concluyente.\n"
    "• Attention y Meditation (eSense, propietarios de NeuroSky) son solo complementarios: NO sustituyen "
    "a EEG1 ni EEG2. Gamma y Delta no se usan como indicadores de carga (Delta solo como control de artefactos).\n"
    "• Etapa 3 (escribir el prompt): al teclear puede haber ruido muscular; interpretarla con cautela."
)
NOTA_ETAPA3 = "Teclado: posible ruido muscular"

# (columna, encabezado, ancho, formato)
COLUMNAS_RESULTADOS = [
    ("participante", "Part.", 55, "P{:.0f}"),
    ("etapa", "Etapa", 70, None),
    ("EEG1_z", "EEG1_z", 70, "{:+.3f}"),
    ("EEG2_z", "EEG2_z", 70, "{:+.3f}"),
    ("lectura", "Lectura", 120, None),
    ("theta_beta_z", "θ/β z", 65, "{:+.3f}"),
    ("engagement_z", "Engag. z", 70, "{:+.3f}"),
    ("duracion_s", "Duración (s)", 90, "{:.0f}"),
    ("attention_prom", "Attention*", 80, "{:.1f}"),
    ("meditation_prom", "Meditation*", 85, "{:.1f}"),
    ("puntaje", "% aciertos", 80, "{:.1f}"),
    ("pct_muestras_validas", "% válido", 70, "{:.1f}"),
    ("nota", "Nota", 200, None),
]
COLUMNAS_ESTADISTICA = [
    ("analisis", "Análisis", 180, None),
    ("indicador", "Indicador", 110, None),
    ("etapa", "Etapa / comparación", 220, None),
    ("n", "n", 40, "{:.0f}"),
    ("estadistico", "Est.", 40, None),
    ("valor", "Valor", 70, "{:.3f}"),
    ("p", "p", 65, "{:.3f}"),
    ("p_holm", "p Holm", 65, "{:.3f}"),
    ("efecto", "Efecto", 100, None),
    ("valor_efecto", "Tamaño", 70, "{:+.3f}"),
    ("significativo", "Sig.", 45, None),
    ("nota", "Nota", 360, None),
]


def _fmt(value, pattern: Optional[str]) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)) or (not isinstance(value, str) and pd.isna(value)):
        return "—"
    if isinstance(value, (bool, np.bool_)):
        return "Sí" if value else "No"
    if pattern is None:
        return str(value)
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
        self.cfg = ConfigAnalisis()
        self.analisis: Optional[ResultadoAnalisis] = None
        self._loading = False
        self._canvases = []
        # (desafío, participante) -> figuras de esa vista (se generan al
        # elegirla y se reutilizan hasta el próximo "Recalcular").
        self._figuras_vista: dict = {}
        self._build()

    # ---------------- Construcción ----------------
    def _font(self, size: int, bold: bool = False) -> ctk.CTkFont:
        return ctk.CTkFont(family=self.font_family, size=self.scaled(size), weight="bold" if bold else "normal")

    def _card(self, parent, title: str) -> ctk.CTkFrame:
        card = ctk.CTkFrame(parent, fg_color=self.c["BG_CARD"], corner_radius=12)
        card.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(card, text=title, font=self._font(13, bold=True)).pack(anchor="w", padx=18, pady=(16, 6))
        return card

    def _muted(self, parent, text: str = "") -> ctk.CTkLabel:
        label = ctk.CTkLabel(
            parent, text=text, font=self._font(11), text_color=self.c["TEXT_MUTED"],
            wraplength=self.scaled(760), justify="left", anchor="w",
        )
        label.pack(fill="x", padx=18, pady=(0, 10))
        return label

    def _tree(self, parent, columns, height: int) -> ttk.Treeview:
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=18, pady=(0, 16))
        frame.grid_columnconfigure(0, weight=1)
        tree = ttk.Treeview(frame, columns=[c for c, *_ in columns], show="headings", height=height)
        for col, label, width, _ in columns:
            tree.heading(col, text=label, anchor="center")
            tree.column(col, width=self.scaled(width), anchor="center", stretch=False)
        tree.tag_configure("baja", foreground=self.c["WARNING"])
        tree.tag_configure("sig", foreground=self.c["ACCENT"])
        tree.grid(row=0, column=0, sticky="ew")
        y_scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        x_scroll = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        return tree

    def _build(self):
        wrapper = ctk.CTkScrollableFrame(self.parent, fg_color="transparent")
        wrapper.pack(fill="both", expand=True, padx=26, pady=(24, 20))

        ctk.CTkLabel(wrapper, text="Análisis EEG", font=self._font(22, bold=True)).pack(anchor="w")
        ctk.CTkLabel(
            wrapper,
            text="EEG1 (Alfa/Theta) y EEG2 (Theta) por etapa, normalizados por participante, "
                 "y su relación con la comprensión.",
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
            button_hover_color=self.c["ACCENT_HOVER"], command=lambda _: self._on_selection_change(),
        )
        self.participant_menu.pack(side="left", padx=(0, 14))
        ctk.CTkLabel(row, text="Desafío", font=self._font(12)).pack(side="left", padx=(0, 8))
        self.challenge_var = ctk.StringVar(value=ALL_CHALLENGES)
        self.challenge_menu = ctk.CTkOptionMenu(
            row, variable=self.challenge_var, values=[ALL_CHALLENGES], width=self.scaled(190),
            font=self._font(12), fg_color=self.c["BG_CARD_ALT"], button_color=self.c["ACCENT"],
            button_hover_color=self.c["ACCENT_HOVER"], command=lambda _: self._on_challenge_change(),
        )
        self.challenge_menu.pack(side="left", padx=(0, 14))
        ctk.CTkButton(
            row, text="🔄  Recalcular", height=self.scaled(32), corner_radius=8, font=self._font(12, bold=True),
            fg_color=self.c["ACCENT"], hover_color=self.c["ACCENT_HOVER"], command=self.refresh,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            row, text="💾  Exportar CSV y PNG", height=self.scaled(32), corner_radius=8, font=self._font(12),
            fg_color=self.c["BG_CARD_ALT"], hover_color=self.c["BORDER"], command=self._export,
        ).pack(side="left")
        self.status_label = ctk.CTkLabel(
            controls, text=f"Fuente: {RUTA_DATASET}", font=self._font(11), text_color=self.c["TEXT_MUTED"],
            anchor="w", justify="left",
        )
        self.status_label.pack(fill="x", padx=18, pady=(0, 14))

        self._muted(self._card(wrapper, "ℹ️  Cómo leer estos valores"), INTERPRETACION)
        self.quality_label = self._muted(self._card(wrapper, "🩺  Calidad de la señal"))

        # Gráficos (uno por tarjeta, se llenan en _render_charts)
        self.chart_holders = {}
        from analisis.graficos import FIGURAS
        for clave, (titulo, _) in FIGURAS.items():
            card = self._card(wrapper, f"📊  {titulo}")
            holder = ctk.CTkFrame(card, fg_color=self.c["BG_CARD"])
            holder.pack(fill="x", padx=18, pady=(0, 16))
            self.chart_holders[clave] = holder

        stats_card = self._card(wrapper, "🧮  Resultados estadísticos")
        self.stats_caption = self._muted(
            stats_card,
            "Friedman (con W de Kendall) entre etapas; si es significativo, Wilcoxon por pares con Holm y r. "
            "Spearman EEG–% de aciertos y Mann-Whitney (alta vs baja comprensión, con r). α = 0,05. "
            "En azul, los resultados significativos. Calculados con todos los desafíos juntos: no cambian "
            "con el selector de desafío.",
        )
        self.stats_tree = self._tree(stats_card, COLUMNAS_ESTADISTICA, height=10)

        table_card = self._card(wrapper, "🧾  Resultados por etapa")
        self._muted(
            table_card,
            "Mediana de los z de cada participante en cada etapa: todos sus desafíos e intentos juntos o, con el "
            "selector, solo el desafío elegido (ahí el % de muestras válidas queda en —: la calidad es por etapa). "
            "* Attention/Meditation: eSense propietario, solo complementario. Etapa 3 sin cuestionario.",
        )
        self.tree = self._tree(table_card, COLUMNAS_RESULTADOS, height=12)

    # ---------------- Datos ----------------
    def refresh(self):
        """Recalcula y exporta en un hilo aparte (lee y procesa todas las
        listas crudas y genera los PNG a 300 dpi; tarda unos segundos)."""
        if self._loading:
            return
        self._loading = True
        self.status_label.configure(text="Calculando…")

        def work():
            try:
                analisis = ejecutar_analisis(RUTA_DATASET, self.cfg)
                carpeta = exportar(analisis)
                error = None
            except Exception as exc:  # se muestra en la pestaña, la app sigue
                analisis, carpeta, error = None, None, exc
            self.parent.after(0, lambda: self._on_loaded(analisis, carpeta, error))

        threading.Thread(target=work, daemon=True).start()

    def refresh_if_needed(self):
        if self.analisis is None:
            self.refresh()

    def _on_loaded(self, analisis: Optional[ResultadoAnalisis], carpeta, error):
        self._loading = False
        if error is not None:
            self.status_label.configure(text=f"⚠️  {error}")
            return
        self.analisis = analisis
        self._figuras_vista = {}
        res = analisis.pipeline.resultados
        participants = sorted(int(p) for p in res["participante"].dropna().unique()) if not res.empty else []
        self._challenge_labels = dict(desafios_disponibles(analisis.por_desafio))
        challenges = [ALL_CHALLENGES] + list(self._challenge_labels.values())
        self.challenge_menu.configure(values=challenges)
        if self.challenge_var.get() not in challenges:
            self.challenge_var.set(ALL_CHALLENGES)
        self._update_participant_options()
        self.status_label.configure(
            text=f"Fuente: {RUTA_DATASET} · {len(participants)} participantes · {len(res)} filas · "
                 f"resultados exportados en {carpeta}"
        )
        self._render_quality()
        self._on_selection_change()

    # ---------------- Selección (participante × desafío) ----------------
    def _selected_participant(self) -> Optional[int]:
        value = self.participant_var.get()
        return None if value == ALL_PARTICIPANTS else int(value.split()[-1])

    def _selected_challenge(self) -> Optional[int]:
        value = self.challenge_var.get()
        return None if value == ALL_CHALLENGES else int(value.split()[1])

    def _vista(self) -> pd.DataFrame:
        """Resultados de la vista actual: todos los desafíos juntos
        (resultados_por_etapa) o solo el desafío elegido."""
        desafio = self._selected_challenge()
        if desafio is None:
            return self.analisis.pipeline.resultados
        return vista_desafio(self.analisis.por_desafio, desafio)

    def _update_participant_options(self):
        """Solo los participantes con datos en el desafío elegido."""
        res = self._vista()
        participants = sorted(int(p) for p in res["participante"].dropna().unique()) if not res.empty else []
        options = [ALL_PARTICIPANTS] + [f"Participante {p}" for p in participants]
        self.participant_menu.configure(values=options)
        if self.participant_var.get() not in options:
            self.participant_var.set(ALL_PARTICIPANTS)

    def _on_challenge_change(self):
        if self.analisis is None:
            return
        self._update_participant_options()
        self._on_selection_change()

    def _on_selection_change(self):
        """Tablas y gráficos de la vista elegida. Desafío: solo ese desafío
        (o todos juntos). Participante: gráficos con sus propios resultados
        (o el grupo). Todos + todos juntos = las figuras ya exportadas."""
        if self.analisis is None:
            return
        self._render_tables()
        participante, desafio = self._selected_participant(), self._selected_challenge()
        res = self._vista()
        if res.empty:
            self._render_charts({}, "Sin datos para esta combinación.")
            return
        if participante is None and desafio is None:
            self._render_charts(self.analisis.figuras)
            return
        clave = (desafio, participante)
        if clave in self._figuras_vista:
            self._render_charts(self._figuras_vista[clave])
            return
        contexto = self._challenge_labels.get(desafio, "") if desafio is not None else ""

        def work():
            from analisis.graficos import generar_figuras
            try:
                figuras, mensaje = generar_figuras(res, self.cfg, participante=participante, contexto=contexto), None
            except Exception as exc:  # la pestaña sigue; se avisa en la tarjeta
                figuras, mensaje = {}, f"No se pudo generar el gráfico: {exc}"
            self.parent.after(0, lambda: self._on_view_figures(clave, figuras, mensaje))

        threading.Thread(target=work, daemon=True).start()

    def _on_view_figures(self, clave: tuple, figuras: dict, mensaje: Optional[str]):
        if mensaje is None:
            self._figuras_vista[clave] = figuras
        if (self._selected_challenge(), self._selected_participant()) == clave:  # puede haber cambiado
            self._render_charts(figuras, mensaje)

    def _export(self):
        if self.analisis is None or self.analisis.pipeline.resultados.empty:
            messagebox.showinfo("Exportar", "Todavía no hay resultados calculados.")
            return
        carpeta = exportar(self.analisis, RUTA_SALIDA)
        messagebox.showinfo(
            "Exportar",
            f"Guardado en:\n{carpeta}\n\nresultados_por_etapa.csv, resultados_estadisticos.csv, "
            "reporte_calidad.csv, resultados_por_desafio.csv y los gráficos del grupo en PNG (300 dpi).",
        )

    # ---------------- Render ----------------
    def _render_quality(self):
        p = self.analisis.pipeline
        cal = p.calidad
        lines = []
        if not cal.empty:
            por_etapa = cal.groupby("etapa")["pct_valido"].mean()
            lines.append(
                f"Muestras válidas (PoorSignal ≤ {self.cfg.umbral_poor_signal}, Theta y Alfa > 0), "
                "promedio por etapa: " + " · ".join(f"{e}: {v:.1f} %" for e, v in por_etapa.items())
            )
            bajas = cal[cal["baja_calidad"]]
            accion = "excluidas del análisis" if self.cfg.excluir_baja_calidad else "incluidas"
            lines.append(
                f"Baja calidad (< {self.cfg.min_pct_valido:.0f} % o < {self.cfg.min_muestras_validas} muestras "
                f"válidas, {accion}): "
                + (", ".join(f"P{r.participante} · {r.etapa}" for r in bajas.itertuples()) or "ninguna")
            )
            lines.append(
                f"Control de artefactos (Delta): {cal['pct_delta_alta'].mean():.1f} % de muestras válidas con "
                f"log Delta > media + {self.cfg.delta_z_artefacto:g} DE del participante (máx. "
                f"{cal['pct_delta_alta'].max():.1f} %)."
            )
        lines.append(
            "Otras etapas en el dataset (fuera del análisis): "
            + (", ".join(p.etapas_ignoradas) if p.etapas_ignoradas else "ninguna")
        )
        lines.append(
            "Línea base: " + (self.cfg.etapa_linea_base or "todas las muestras válidas de las Etapas 2–5 del participante")
        )
        otros = [a for a in p.avisos if "baja calidad" not in a]
        if otros:
            lines.append("Avisos: " + " ".join(otros[:6]) + (f" (+{len(otros) - 6} más)" if len(otros) > 6 else ""))
        por_desafio = self.analisis.avisos_por_desafio
        if por_desafio:
            lines.append("Vista por desafío: " + " ".join(por_desafio[:4])
                         + (f" (+{len(por_desafio) - 4} más)" if len(por_desafio) > 4 else ""))
        self.quality_label.configure(text="\n".join(lines))

    def _render_charts(self, figuras: Optional[dict] = None, mensaje: Optional[str] = None):
        figuras = self.analisis.figuras if figuras is None else figuras
        for canvas in self._canvases:
            canvas.get_tk_widget().destroy()
        self._canvases = []
        for clave, holder in self.chart_holders.items():
            for child in holder.winfo_children():
                child.destroy()
            fig = figuras.get(clave)
            if FigureCanvasTkAgg is None or fig is None:
                ctk.CTkLabel(
                    holder, text=mensaje or "Gráfico no disponible (sin datos o sin matplotlib).", font=self._font(11),
                    text_color=self.c["TEXT_MUTED"],
                ).pack(anchor="w")
                continue
            canvas = FigureCanvasTkAgg(fig, master=holder)
            canvas.draw()
            canvas.get_tk_widget().pack(anchor="w")
            self._canvases.append(canvas)

    def _render_tables(self):
        if self.analisis is None:
            return
        participante = self._selected_participant()
        res = self._vista().copy()
        if participante is not None:
            res = res[res["participante"] == participante]
        res["lectura"] = [interpretar_carga(a, b) for a, b in zip(res["EEG1_z"], res["EEG2_z"])]
        res["nota"] = np.where(res["etapa"] == self.cfg.etapa_sin_cuestionario, NOTA_ETAPA3, "")
        self.tree.delete(*self.tree.get_children())
        for _, row in res.iterrows():
            self.tree.insert(
                "", "end", values=[_fmt(row.get(c), f) for c, _, _, f in COLUMNAS_RESULTADOS],
            )

        est = self.analisis.estadistica
        self.stats_tree.delete(*self.stats_tree.get_children())
        for _, row in est.iterrows():
            values = []
            for c, _, _, f in COLUMNAS_ESTADISTICA:
                v = row.get(c)
                if c == "nota" and isinstance(v, str):
                    v = v.replace(f"; {NOTA_MUESTRA_PEQUENA}", "").replace(NOTA_MUESTRA_PEQUENA, "") or "—"
                values.append(_fmt(v, f))
            sig = row.get("significativo")
            tags = ("sig",) if isinstance(sig, (bool, np.bool_)) and sig else ()
            self.stats_tree.insert("", "end", values=values, tags=tags)
        if not est.empty and est["nota"].astype(str).str.contains(NOTA_MUESTRA_PEQUENA).any():
            self.stats_caption.configure(
                text=f"⚠️ {NOTA_MUESTRA_PEQUENA.capitalize()} "
                     f"(n = {self.analisis.pipeline.resultados['participante'].nunique()}; el modelo lineal mixto "
                     f"requiere ≥ {self.cfg.min_participantes_modelo_mixto} participantes). "
                     "Friedman (W de Kendall) entre etapas → Wilcoxon por pares con Holm y r si es significativo; "
                     "Spearman EEG–% de aciertos; Mann-Whitney alta vs baja (r). α = 0,05. "
                     "En azul, los resultados significativos."
            )
