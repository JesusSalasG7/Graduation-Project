"""Gráficos del análisis EEG (matplotlib, sin pyplot para poder generarlos
fuera del hilo de la interfaz). Cada función devuelve una Figure: la
pestaña Análisis la embebe y guardar_figuras la exporta en PNG a 300 dpi.

Con TIPO_GRAFICO = "barras" (por defecto) se generan:
  1. perfil_etapas            barras: mediana del grupo por etapa + un punto por participante
  2. comprension_alta_vs_baja barras agrupadas alta/baja con el p de Mann-Whitney
  3. eeg_vs_comprension       dispersión EEG vs % de aciertos (ρ de Spearman)
  4. resumen_etapas           EEG1 y EEG2 por etapa en un solo gráfico
Los gráficos anteriores (líneas por participante y boxplots) siguen al final
del archivo y se reactivan con TIPO_GRAFICO = "boxplot" o "lineas".

Convenciones: ejes de EEG en unidades z (0 = nivel habitual del
participante, línea sólida), EEG1 en morado y EEG2 en verde azulado, y las
etapas rotuladas "Etapa N" con su descripción corta debajo. Los textos de
interpretación usan coma decimal.
"""

import inspect
import textwrap
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter

from analisis.config import (
    COLOR_COMPARACION, COLOR_EEG1, COLOR_EEG2, DPI_EXPORTACION, MOSTRAR_RIC, TIPO_GRAFICO,
    UMBRAL_CERCANO_Z, ConfigAnalisis,
)
from analisis.estadistica import grupos_comprension, mann_whitney_comprension, spearman_panel

PANELES = [
    ("EEG1_z", "EEG1 · Alfa/Theta (z)", COLOR_EEG1),
    ("EEG2_z", "EEG2 · Theta (z)", COLOR_EEG2),
]
# Qué significa subir o bajar en cada indicador (flechas junto al eje Y).
FLECHAS = {
    "EEG1_z": ("↑ menos carga / más relajación", "↓ más carga cognitiva"),
    "EEG2_z": ("↑ más carga de memoria de trabajo", "↓ menos demanda"),
}
NOMBRE_CORTO = {"EEG1_z": "EEG1", "EEG2_z": "EEG2"}
ETIQUETA_Y = "z (0 = nivel habitual del participante)"
GRIS = "#8a8a8a"
GRIS_CLARO = "#c4c4c4"
TINTA = "#2b2b2b"
TINTA_SUAVE = "#5f5f5f"
SOMBRA_ETAPA3 = "#efefef"
COLOR_PUNTOS = "#2b2b2b"
# Participante elegido en la pestaña: en la dispersión (Figura 3, que
# necesita a todo el grupo) sus puntos llevan un anillo naranja.
COLOR_DESTACADO = "#E8590C"
COLOR_PUNTAJE = "#5F5E5A"  # % de aciertos con comprensión alta (vista por participante)
ALTO_LINEA_PIE = 0.19  # pulgadas por línea del texto de interpretación


def etiqueta_etapa(etapa: str, cfg: ConfigAnalisis = ConfigAnalisis()) -> str:
    """"Etapa 2" -> "Etapa 2\\nProblema"."""
    corta = cfg.descripcion_corta.get(etapa, "")
    return f"{etapa}\n{corta}" if corta else etapa


def _estilo(ax, titulo: str, ylabel: str = "z"):
    ax.set_title(titulo, fontsize=11, color=TINTA, loc="left", fontweight="bold")
    ax.set_ylabel(ylabel, fontsize=9, color=TINTA_SUAVE)
    ax.axhline(0, color=TINTA_SUAVE, linestyle=":", linewidth=1, zorder=1)
    ax.tick_params(colors=TINTA_SUAVE, labelsize=8.5)
    ax.grid(axis="y", color="#ececec", linewidth=0.6, zorder=0)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(GRIS_CLARO)


def _sombrear_etapa3(ax, etapas: list[str], cfg: ConfigAnalisis):
    if cfg.etapa_sin_cuestionario not in etapas:
        return
    x = etapas.index(cfg.etapa_sin_cuestionario)
    ax.axvspan(x - 0.5, x + 0.5, color=SOMBRA_ETAPA3, zorder=0)
    ax.text(x, 0.98, "sin cuestionario", transform=ax.get_xaxis_transform(), ha="center", va="top",
            fontsize=8, color=TINTA_SUAVE, style="italic")


def _ejes_etapas(ax, etapas: list[str], cfg: ConfigAnalisis):
    ax.set_xticks(range(len(etapas)))
    ax.set_xticklabels([etiqueta_etapa(e, cfg) for e in etapas], fontsize=8.5, color=TINTA)
    ax.set_xlim(-0.5, len(etapas) - 0.5)


# ============================================================
# Textos (coma decimal) e interpretación automática
# ============================================================

def num(valor: float, signo: bool = True, decimales: int = 2) -> str:
    """0.5512 -> "+0,55"; -0.5 -> "−0,50" (signo menos tipográfico)."""
    if valor is None or not np.isfinite(valor):
        return "—"
    texto = f"{valor:+.{decimales}f}" if signo else f"{valor:.{decimales}f}"
    if texto.lstrip("+-").strip("0,.") == "":  # -0,00 -> 0,00
        texto = f"{0:.{decimales}f}"
    return texto.replace("-", "−").replace(".", ",")


def asteriscos(p: float, alfa: float = 0.05) -> str:
    if p is None or not np.isfinite(p):
        return ""
    if p < 0.01:
        return "**"
    return "*" if p < alfa else "n.s."


def texto_p(p: float, alfa: float = 0.05) -> str:
    if p is None or not np.isfinite(p):
        return "p no calculable"
    valor = "p < 0,001" if p < 0.001 else f"p = {num(p, signo=False, decimales=3)}"
    return f"{valor} {asteriscos(p, alfa)}"


def patron_carga(eeg1: float, eeg2: float, umbral: float = UMBRAL_CERCANO_Z) -> str:
    """Lectura conjunta de las medianas de EEG1_z y EEG2_z:
    |ambas| < umbral -> cercano al nivel habitual (se añade la dirección si
    la hay); EEG1 < 0 y EEG2 > 0 -> mayor carga; EEG1 > 0 y EEG2 < 0 ->
    menor carga; si se contradicen -> no concluyente."""
    if not (np.isfinite(eeg1) and np.isfinite(eeg2)):
        return "sin datos suficientes"
    if eeg1 < 0 and eeg2 > 0:
        direccion = "mayor carga cognitiva"
    elif eeg1 > 0 and eeg2 < 0:
        direccion = "menor carga cognitiva"
    else:
        direccion = None
    if abs(eeg1) < umbral and abs(eeg2) < umbral:
        return "cercano al nivel habitual" + (f" (en la dirección de {direccion})" if direccion else "")
    return f"patrón de {direccion}" if direccion else "resultado no concluyente"


def misma_direccion(df: pd.DataFrame, med1: float, med2: float) -> tuple[int, int]:
    """Participantes cuyo EEG1_z y EEG2_z tienen el mismo signo que las
    medianas del grupo (y cuántos tienen ambos valores)."""
    df = df.dropna(subset=["EEG1_z", "EEG2_z"])
    iguales = (np.sign(df["EEG1_z"]) == np.sign(med1)) & (np.sign(df["EEG2_z"]) == np.sign(med2))
    return int(iguales.sum()), len(df)


def interpretacion_etapas(resultados: pd.DataFrame, cfg: ConfigAnalisis = ConfigAnalisis()) -> list[str]:
    """Una frase por etapa para el pie de la Figura 1."""
    lineas = []
    for etapa in cfg.etapas_analisis:
        df = resultados[resultados["etapa"] == etapa]
        m1, m2 = df["EEG1_z"].median(), df["EEG2_z"].median()
        if not (np.isfinite(m1) and np.isfinite(m2)):
            lineas.append(f"En la {etapa} no hay datos suficientes.")
            continue
        k, n = misma_direccion(df, m1, m2)
        patron = patron_carga(m1, m2)
        conteo = (f"{k} de {n} participantes siguieron esta tendencia." if "carga" in patron else
                  f"{k} de {n} participantes tuvieron el mismo signo que la mediana en ambos indicadores.")
        lineas.append(f"En la {etapa} la mediana de EEG1 fue {num(m1)} y la de EEG2 {num(m2)}: {patron}. {conteo}")
    return lineas


def _titulo_destacado(participante: Optional[int]) -> str:
    if participante is None:
        return ""
    return f"\nAnillo naranja: Participante {participante} (la correlación se calcula con todo el grupo)"


# ============================================================
# Piezas comunes de los gráficos de barras
# ============================================================

def _tick(v, _=None) -> str:
    """Número de un eje con coma decimal y solo los decimales necesarios
    (0,25 no se redondea a 0,2)."""
    texto = f"{v:.3f}".rstrip("0")
    texto = texto + "0" if texto.endswith(".") else texto
    return num(float(texto), signo=False, decimales=len(texto.split(".")[1]))


def _formato_coma(ax):
    ax.yaxis.set_major_formatter(FuncFormatter(_tick))


def _estilo_barras(ax, titulo: str, col: str = None, flechas: bool = True):
    """Título, etiqueta del eje Y, línea sólida en 0 y (si col) las dos
    flechas de texto que explican qué significa subir o bajar."""
    ax.set_title(titulo, fontsize=11, color=TINTA, loc="left", fontweight="bold")
    ax.set_ylabel(ETIQUETA_Y, fontsize=8.5, color=TINTA_SUAVE, labelpad=24 if (flechas and col) else 4)
    ax.axhline(0, color=TINTA, linestyle="-", linewidth=1, zorder=3)
    ax.tick_params(colors=TINTA_SUAVE, labelsize=8.5)
    ax.grid(axis="y", color="#ececec", linewidth=0.6, zorder=0)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(GRIS_CLARO)
    _formato_coma(ax)
    if flechas and col in FLECHAS:
        arriba, abajo = FLECHAS[col]
        color = dict((c, k) for c, _, k in PANELES)[col]
        # Rotadas en el margen izquierdo, entre los números del eje y su
        # etiqueta: la de arriba sube desde z = 0 y la de abajo baja. Los
        # límites ya son simétricos (_limites_simetricos), así que z = 0 es
        # la mitad del eje.
        y0 = ax.transLimits.transform((0, 0))[1]
        comun = dict(xycoords="axes fraction", textcoords="offset points", rotation=90,
                     rotation_mode="anchor", va="bottom", fontsize=7, color=color, fontweight="bold")
        ax.annotate(arriba, (0, y0), xytext=(-38, 4), ha="left", **comun)
        ax.annotate(abajo, (0, y0), xytext=(-38, -4), ha="right", **comun)


def _limites_simetricos(ax, valores, margen: float = 1.45):
    """Límites del eje Y simétricos alrededor de 0 (0 queda en el centro,
    así "arriba" y "abajo" se leen igual en todos los paneles)."""
    v = np.asarray([x for x in valores if x is not None and np.isfinite(x)], dtype=float)
    tope = float(np.max(np.abs(v))) if v.size else 1.0
    tope = max(tope, 0.05) * margen
    ax.set_ylim(-tope, tope)
    return tope


def _barras(ax, posiciones, series, color, rng, ancho=0.6, puntos=True,
            mostrar_ric: bool = MOSTRAR_RIC, etiquetas=True) -> list[float]:
    """Barra = mediana del grupo (desde 0), un punto oscuro por participante
    con jitter horizontal, RIC opcional y el valor de la mediana encima (si
    es positiva) o debajo (si es negativa), más allá del punto más extremo."""
    medianas = []
    for x, valores in zip(posiciones, series):
        v = np.asarray(valores, dtype=float)
        v = v[np.isfinite(v)]
        if not v.size:
            medianas.append(float("nan"))
            continue
        med = float(np.median(v))
        medianas.append(med)
        ax.bar(x, med, width=ancho, color=color, zorder=2, edgecolor="none")
        if mostrar_ric:
            q1, q3 = np.percentile(v, [25, 75])
            ax.errorbar(x, med, yerr=[[med - q1], [q3 - med]], fmt="none", ecolor=TINTA_SUAVE,
                        elinewidth=1, capsize=3, zorder=4)
        if puntos:
            jitter = rng.uniform(-ancho * 0.28, ancho * 0.28, size=v.size)
            ax.scatter(np.full(v.size, x) + jitter, v, s=13, color=COLOR_PUNTOS, alpha=0.8,
                       linewidth=0, zorder=5)
        if etiquetas:
            extremos = [med] + (list(v) if puntos else [])
            if mostrar_ric:
                extremos += [q1, q3]
            arriba = med >= 0
            y = max(extremos) if arriba else min(extremos)
            ax.annotate(num(med), (x, y), xytext=(0, 4 if arriba else -4), textcoords="offset points",
                        ha="center", va="bottom" if arriba else "top", fontsize=8, color=TINTA,
                        fontweight="bold", zorder=6)
    return medianas


def _pie(fig: Figure, lineas: list[str], ancho_caracteres: int = 150):
    """Texto de interpretación debajo de la figura. Agranda la figura para
    que los gráficos no pierdan altura y devuelve la fracción reservada."""
    envuelto = []
    for linea in lineas:
        envuelto += textwrap.wrap(linea, ancho_caracteres) or [""]
    ancho, alto = fig.get_size_inches()
    extra = ALTO_LINEA_PIE * len(envuelto) + 0.2
    fig.set_size_inches(ancho, alto + extra)
    fraccion = extra / (alto + extra)
    fig.text(0.012, fraccion - 0.06 / (alto + extra), "\n".join(envuelto), ha="left", va="top",
             fontsize=8.5, color=TINTA, linespacing=1.45)
    return fraccion


def _maquetar(fig: Figure, pie: float = 0.0, arriba: float = 0.94):
    fig.tight_layout(rect=(0, pie, 1, arriba))


# ============================================================
# Figura 1. Perfil de carga por etapa (barras)
# ============================================================

def grafico_perfil_barras(resultados: pd.DataFrame, cfg: ConfigAnalisis = ConfigAnalisis(),
                          mostrar_ric: bool = MOSTRAR_RIC, participante: Optional[int] = None) -> Figure:
    """Dos paneles (EEG1_z, EEG2_z): una barra por etapa con la mediana del
    grupo y un punto por participante. Con `participante`, las barras son
    los valores de esa persona (grafico_perfil_participante)."""
    if participante is not None:
        return grafico_perfil_participante(resultados, cfg, participante)
    etapas = list(cfg.etapas_analisis)
    rng = np.random.default_rng(0)
    fig = Figure(figsize=(11, 5.3), dpi=100, facecolor="white")
    axes = fig.subplots(1, 2)
    x = list(range(len(etapas)))
    for ax, (col, titulo, color) in zip(axes, PANELES):
        _sombrear_etapa3(ax, etapas, cfg)
        series = [resultados.loc[resultados["etapa"] == e, col] for e in etapas]
        _limites_simetricos(ax, pd.concat(series).tolist())
        _barras(ax, x, series, color, rng, mostrar_ric=mostrar_ric)
        _ejes_etapas(ax, etapas, cfg)
        _estilo_barras(ax, titulo, col)
    pie = _pie(fig, interpretacion_etapas(resultados, cfg))
    fig.suptitle(f"Perfil de carga por etapa · barra = mediana del grupo, punto = participante "
                 f"(n = {resultados['participante'].nunique()})",
                 fontsize=10, color=TINTA_SUAVE, x=0.01, ha="left")
    _maquetar(fig, pie)
    return fig


def _datos_participante(resultados: pd.DataFrame, participante: int, etapas: list[str]) -> pd.DataFrame:
    """Filas del participante indexadas por etapa (NaN donde no hay datos)."""
    propio = resultados[resultados["participante"] == participante].drop_duplicates("etapa")
    return propio.set_index("etapa").reindex(etapas)


def _sin_datos(ax, posiciones, valores):
    for x, v in zip(posiciones, valores):
        if not np.isfinite(v):
            ax.text(x, 0, "sin datos", ha="center", va="bottom", fontsize=7.5, color=TINTA_SUAVE,
                    style="italic", zorder=6)


def grafico_perfil_participante(resultados: pd.DataFrame, cfg: ConfigAnalisis, participante: int) -> Figure:
    """Figura 1 de un participante: una barra por etapa con SU valor z (su
    propia escala del eje Y), sin puntos ni medianas del grupo."""
    etapas = list(cfg.etapas_analisis)
    d = _datos_participante(resultados, participante, etapas)
    fig = Figure(figsize=(11, 5.3), dpi=100, facecolor="white")
    axes = fig.subplots(1, 2)
    x = list(range(len(etapas)))
    rng = np.random.default_rng(0)
    for ax, (col, titulo, color) in zip(axes, PANELES):
        _sombrear_etapa3(ax, etapas, cfg)
        valores = d[col].to_numpy(dtype=float)
        _limites_simetricos(ax, valores.tolist())
        _barras(ax, x, [[v] for v in valores], color, rng, puntos=False, mostrar_ric=False)
        _sin_datos(ax, x, valores)
        _ejes_etapas(ax, etapas, cfg)
        _estilo_barras(ax, titulo, col)
    lineas = []
    for etapa in etapas:
        e1, e2 = float(d.loc[etapa, "EEG1_z"]), float(d.loc[etapa, "EEG2_z"])
        if not (np.isfinite(e1) and np.isfinite(e2)):
            lineas.append(f"En la {etapa} no hay datos válidos de este participante.")
            continue
        lineas.append(f"En la {etapa} EEG1 fue {num(e1)} y EEG2 {num(e2)}: {patron_carga(e1, e2)}.")
    etapa, med = etapa_mayor_carga(resultados[resultados["participante"] == participante], cfg)
    if etapa is not None:
        lineas.append(f"Su etapa de mayor carga: {etapa} (EEG2_z − EEG1_z = {num(med.loc[etapa, 'diferencia'])}).")
    pie = _pie(fig, lineas)
    fig.suptitle(f"Participante {participante} · perfil de carga por etapa (sus propios valores z)",
                 fontsize=10, color=TINTA_SUAVE, x=0.01, ha="left")
    _maquetar(fig, pie)
    return fig


# ============================================================
# Figura 2. EEG según nivel de comprensión (barras agrupadas)
# ============================================================

def grafico_alta_vs_baja_barras(resultados: pd.DataFrame, cfg: ConfigAnalisis = ConfigAnalisis(),
                                mostrar_ric: bool = MOSTRAR_RIC, participante: Optional[int] = None) -> Figure:
    """En cada etapa con cuestionario, barra de color = comprensión alta
    (≥ mediana del puntaje de esa etapa) y gris = baja, con el p de
    Mann-Whitney (estadistica.mann_whitney_comprension) sobre cada par.
    Con `participante`: grafico_comprension_participante."""
    if participante is not None:
        return grafico_comprension_participante(resultados, cfg, participante)
    etapas = list(cfg.etapas_con_cuestionario)
    df = grupos_comprension(resultados, cfg)
    mw = pd.DataFrame(mann_whitney_comprension(resultados, cfg))
    rng = np.random.default_rng(1)
    fig = Figure(figsize=(11, 5.3), dpi=100, facecolor="white")
    axes = fig.subplots(1, 2)
    x = np.arange(len(etapas))
    dx, ancho = 0.2, 0.36
    grupos = (("Comprensión alta", -dx), ("Comprensión baja", dx))
    medianas = {}
    for ax, (col, titulo, color) in zip(axes, PANELES):
        _limites_simetricos(ax, df[col].tolist(), margen=1.6)
        for grupo, desplazamiento in grupos:
            c = color if grupo.endswith("alta") else COLOR_COMPARACION
            series = [df.loc[(df["etapa"] == e) & (df["grupo"] == grupo), col] for e in etapas]
            medianas[(col, grupo)] = _barras(ax, list(x + desplazamiento), series, c, rng, ancho=ancho,
                                             mostrar_ric=mostrar_ric)
        for xi, etapa in zip(x, etapas):
            fila = mw[(mw["indicador"] == col) & (mw["etapa"] == etapa)]
            p = float(fila["p"].iloc[0]) if len(fila) else float("nan")
            ax.annotate("", (xi - dx, 0.9), (xi + dx, 0.9), xycoords=("data", "axes fraction"),
                        arrowprops=dict(arrowstyle="-", color=TINTA_SUAVE, linewidth=0.8))
            ax.text(xi, 0.91, texto_p(p, cfg.alfa), transform=ax.get_xaxis_transform(), ha="center",
                    va="bottom", fontsize=8, color=TINTA)
        _ejes_etapas(ax, etapas, cfg)
        _estilo_barras(ax, titulo, col)
        ax.legend(handles=[Patch(color=color, label="Comprensión alta"),
                           Patch(color=COLOR_COMPARACION, label="Comprensión baja")],
                  frameon=False, fontsize=8, loc="lower right", bbox_to_anchor=(1, 1.01), ncol=2,
                  handlelength=1.2, columnspacing=1)

    lineas = []
    for i, etapa in enumerate(etapas):
        sub = df[df["etapa"] == etapa]
        n_alta = int((sub["grupo"] == "Comprensión alta").sum())
        n_baja = int((sub["grupo"] == "Comprensión baja").sum())
        a1, a2 = medianas[("EEG1_z", "Comprensión alta")][i], medianas[("EEG2_z", "Comprensión alta")][i]
        b1, b2 = medianas[("EEG1_z", "Comprensión baja")][i], medianas[("EEG2_z", "Comprensión baja")][i]
        ps = [mw[(mw["indicador"] == c) & (mw["etapa"] == etapa)]["p"] for c in ("EEG1_z", "EEG2_z")]
        ps = [float(p.iloc[0]) if len(p) else float("nan") for p in ps]
        sig = [NOMBRE_CORTO[c] for c, p in zip(("EEG1_z", "EEG2_z"), ps) if np.isfinite(p) and p < cfg.alfa]
        cierre = (f"diferencia significativa en {' y '.join(sig)}." if sig
                  else "sin diferencias significativas entre grupos.")
        lineas.append(
            f"{etapa}: comprensión alta (n = {n_alta}) EEG1 {num(a1)} / EEG2 {num(a2)}, {patron_carga(a1, a2)}; "
            f"comprensión baja (n = {n_baja}) EEG1 {num(b1)} / EEG2 {num(b2)}, {patron_carga(b1, b2)}; {cierre}"
        )
    pie = _pie(fig, lineas)
    fig.suptitle("EEG según nivel de comprensión · alta = puntaje ≥ mediana de la etapa · "
                 "p de Mann-Whitney (* p<0,05, ** p<0,01, n.s. no significativo)",
                 fontsize=10, color=TINTA_SUAVE, x=0.01, ha="left")
    _maquetar(fig, pie, arriba=0.93)
    return fig


def grafico_comprension_participante(resultados: pd.DataFrame, cfg: ConfigAnalisis, participante: int) -> Figure:
    """Figura 2 de un participante, solo en las etapas con cuestionario.
    Izquierda: su % de aciertos (oscuro = comprensión alta, gris = baja,
    según la mediana del grupo en esa etapa, marcada con una raya).
    Derecha: su EEG1_z y EEG2_z en esas mismas etapas."""
    etapas = list(cfg.etapas_con_cuestionario)
    grupos = grupos_comprension(resultados, cfg)
    propio = grupos[grupos["participante"] == participante].drop_duplicates("etapa").set_index("etapa")
    propio = propio.reindex(etapas)
    med_grupo = grupos.groupby("etapa")["puntaje"].median().reindex(etapas)
    d = _datos_participante(resultados, participante, etapas)
    fig = Figure(figsize=(11, 5.0), dpi=100, facecolor="white")
    ax_q, ax_eeg = fig.subplots(1, 2, gridspec_kw={"width_ratios": [1, 1.25]})
    x = np.arange(len(etapas))

    # Comprensión
    for xi, etapa in zip(x, etapas):
        puntaje, grupo = propio.loc[etapa, "puntaje"], propio.loc[etapa, "grupo"]
        if pd.notna(puntaje):
            alta = grupo == "Comprensión alta"
            ax_q.bar(xi, puntaje, width=0.55, color=COLOR_PUNTAJE if alta else COLOR_COMPARACION, zorder=2)
            ax_q.text(xi, puntaje + 1.5, f"{num(float(puntaje), signo=False, decimales=0)} %", ha="center",
                      va="bottom", fontsize=8.5, color=TINTA, fontweight="bold")
            ax_q.text(xi, 4, "alta" if alta else "baja", ha="center", va="bottom", fontsize=8,
                      color="white" if alta else TINTA, zorder=3)
        else:
            ax_q.text(xi, 2, "sin datos", ha="center", va="bottom", fontsize=7.5, color=TINTA_SUAVE, style="italic")
        if pd.notna(med_grupo.loc[etapa]):
            ax_q.hlines(med_grupo.loc[etapa], xi - 0.38, xi + 0.38, color=TINTA, linestyle="--", linewidth=1.1,
                        zorder=4)
    ax_q.set_ylim(0, 112)
    _ejes_etapas(ax_q, etapas, cfg)
    ax_q.set_title("Comprensión (% de aciertos)", fontsize=11, color=TINTA, loc="left", fontweight="bold")
    ax_q.set_ylabel("% de aciertos", fontsize=8.5, color=TINTA_SUAVE)
    ax_q.tick_params(colors=TINTA_SUAVE, labelsize=8.5)
    ax_q.grid(axis="y", color="#ececec", linewidth=0.6, zorder=0)
    for lado in ("top", "right"):
        ax_q.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax_q.spines[lado].set_color(GRIS_CLARO)
    ax_q.legend(handles=[Patch(color=COLOR_PUNTAJE, label="alta (≥ mediana)"),
                         Patch(color=COLOR_COMPARACION, label="baja"),
                         Line2D([], [], color=TINTA, linestyle="--", label="mediana del grupo")],
                frameon=False, fontsize=7.5, loc="lower right", bbox_to_anchor=(1, 1.06), ncol=3,
                handlelength=1.4, columnspacing=0.8)

    # EEG en las mismas etapas
    rng = np.random.default_rng(1)
    dx, ancho = 0.19, 0.36
    _limites_simetricos(ax_eeg, d[["EEG1_z", "EEG2_z"]].to_numpy().ravel().tolist(), margen=1.5)
    for (col, _, color), desplazamiento in zip(PANELES, (-dx, dx)):
        valores = d[col].to_numpy(dtype=float)
        _barras(ax_eeg, list(x + desplazamiento), [[v] for v in valores], color, rng, ancho=ancho, puntos=False,
                mostrar_ric=False)
        _sin_datos(ax_eeg, list(x + desplazamiento), valores)
    _ejes_etapas(ax_eeg, etapas, cfg)
    _estilo_barras(ax_eeg, "Carga (EEG) en esas etapas", flechas=False)
    ax_eeg.legend(handles=[Patch(color=COLOR_EEG1, label="EEG1 (más bajo = más carga)"),
                           Patch(color=COLOR_EEG2, label="EEG2 (más alto = más carga)")],
                  frameon=False, fontsize=7.5, loc="lower right", bbox_to_anchor=(1, 1.06), ncol=2,
                  handlelength=1.2)

    lineas = []
    for etapa in etapas:
        puntaje = propio.loc[etapa, "puntaje"]
        e1, e2 = float(d.loc[etapa, "EEG1_z"]), float(d.loc[etapa, "EEG2_z"])
        if pd.isna(puntaje):
            lineas.append(f"{etapa}: sin puntaje del cuestionario.")
            continue
        texto = (f"{etapa}: {num(float(puntaje), signo=False, decimales=0)} % de aciertos (mediana del grupo "
                 f"{num(float(med_grupo.loc[etapa]), signo=False, decimales=0)} %) → "
                 f"{propio.loc[etapa, 'grupo'].lower()}")
        if np.isfinite(e1) and np.isfinite(e2):
            texto += f"; EEG1 {num(e1)} / EEG2 {num(e2)} → {patron_carga(e1, e2)}."
        else:
            texto += "; sin EEG válido en esta etapa."
        lineas.append(texto)
    pie = _pie(fig, lineas)
    fig.suptitle(f"Participante {participante} · comprensión y carga en las etapas con cuestionario",
                 fontsize=10, color=TINTA_SUAVE, x=0.01, ha="left")
    _maquetar(fig, pie, arriba=0.95)
    return fig


# ============================================================
# Figura 3. Relación EEG–comprensión (dispersión)
# ============================================================

def frase_spearman(col: str, rho: float, p: float, alfa: float = 0.05) -> str:
    """Lectura en palabras de ρ para el pie de cada panel."""
    if rho is None or not np.isfinite(rho):
        return "ρ no calculable"
    if rho == 0:
        frase = "sin relación"
    elif col == "EEG1_z":
        frase = "a menor carga, mejor comprensión" if rho > 0 else "a mayor carga, mejor comprensión"
    else:
        frase = "a mayor Theta, peor comprensión" if rho < 0 else "a mayor Theta, mejor comprensión"
    if not np.isfinite(p) or p >= alfa:
        frase += "\n(tendencia no significativa)"
    return frase


def grafico_eeg_vs_comprension(resultados: pd.DataFrame, cfg: ConfigAnalisis = ConfigAnalisis(),
                               participante: Optional[int] = None) -> Figure:
    """Cuadrícula 2 × 3: filas EEG1_z / EEG2_z, columnas las etapas con
    cuestionario. EEG en el eje X, % de aciertos en el Y, tamaño del punto
    proporcional a la duración de la etapa y recta de tendencia (mínimos
    cuadrados, solo orientativa: la prueba es Spearman). Debajo de cada
    panel, la lectura en palabras de ρ."""
    etapas = list(cfg.etapas_con_cuestionario)
    fig = Figure(figsize=(11, 7.8), dpi=100, facecolor="white")
    axes = fig.subplots(2, len(etapas), squeeze=False, sharey=True)
    dur = resultados["duracion_s"].astype(float)
    dur_max = dur[resultados["etapa"].isin(etapas)].max()
    for fila_ax, (col, titulo_ind, color) in zip(axes, PANELES):
        for ax, etapa in zip(fila_ax, etapas):
            df = resultados[(resultados["etapa"] == etapa)].dropna(subset=[col, "puntaje"])
            if dur_max and np.isfinite(dur_max):
                tam = 25 + 175 * df["duracion_s"].astype(float).fillna(0) / dur_max
            else:
                tam = 50
            ax.scatter(df[col], df["puntaje"], s=tam, color=color, alpha=0.75, edgecolor="white",
                       linewidth=1, zorder=3)
            for _, r in df.iterrows():
                ax.annotate(f"P{r['participante']}", (r[col], r["puntaje"]), xytext=(5, 3),
                            textcoords="offset points", fontsize=6.5, color=GRIS)
            if participante is not None:
                propio = df[df["participante"] == participante]
                ax.scatter(propio[col], propio["puntaje"], s=150, facecolor="none", edgecolor=COLOR_DESTACADO,
                           linewidth=2.2, zorder=6)
            if len(df) >= 3 and df[col].nunique() > 1:
                pendiente, ordenada = np.polyfit(df[col], df["puntaje"], 1)
                xs = np.linspace(df[col].min(), df[col].max(), 20)
                ax.plot(xs, pendiente * xs + ordenada, color=color, linewidth=1.6, linestyle="-", zorder=2)
            rho, p, n = spearman_panel(df, col)
            sub = (f"ρ = {num(rho)}, {texto_p(p, cfg.alfa)} (n = {n})" if np.isfinite(rho)
                   else f"ρ no calculable (n = {n})")
            corta = cfg.descripcion_corta.get(etapa, "")
            ax.set_title(f"{etapa} · {corta}\n{sub}", fontsize=9.5, color=TINTA, loc="left")
            ax.axvline(0, color=TINTA_SUAVE, linestyle=":", linewidth=1, zorder=1)
            ax.set_xlabel(f"{titulo_ind} · 0 = nivel habitual", fontsize=8.5, color=TINTA_SUAVE)
            ax.annotate(frase_spearman(col, rho, p, cfg.alfa), (0, 0), xycoords="axes fraction",
                        xytext=(0, -34), textcoords="offset points", ha="left", va="top", fontsize=8,
                        color=TINTA, style="italic")
            ax.tick_params(colors=TINTA_SUAVE, labelsize=8)
            ax.xaxis.set_major_formatter(FuncFormatter(_tick))
            ax.grid(color="#ececec", linewidth=0.6, zorder=0)
            for lado in ("top", "right"):
                ax.spines[lado].set_visible(False)
            for lado in ("left", "bottom"):
                ax.spines[lado].set_color(GRIS_CLARO)
        fila_ax[0].set_ylabel("% de aciertos", fontsize=9, color=TINTA_SUAVE)
    fig.suptitle("Relación EEG–comprensión · tamaño del punto ∝ duración de la etapa · ρ de Spearman"
                 + _titulo_destacado(participante),
                 fontsize=10, color=TINTA_SUAVE, x=0.01, ha="left")
    fig.tight_layout(h_pad=2.2)
    return fig


# ============================================================
# Figura 4. Comparación rápida de etapas (resumen)
# ============================================================

def etapa_mayor_carga(resultados: pd.DataFrame, cfg: ConfigAnalisis = ConfigAnalisis()):
    """Etapa con mayor EEG2_z − EEG1_z (medianas del grupo): EEG1 más
    negativo y EEG2 más positivo = más carga. Devuelve (etapa, tabla)."""
    med = resultados.groupby("etapa")[["EEG1_z", "EEG2_z"]].median().reindex(list(cfg.etapas_analisis))
    med["diferencia"] = med["EEG2_z"] - med["EEG1_z"]
    validas = med["diferencia"].dropna()
    return (validas.idxmax() if len(validas) else None), med


def grafico_resumen_etapas(resultados: pd.DataFrame, cfg: ConfigAnalisis = ConfigAnalisis(),
                           participante: Optional[int] = None) -> Figure:
    """Barras agrupadas: en cada etapa, la mediana del grupo de EEG1_z
    (morado) y de EEG2_z (verde azulado), sin puntos. Con `participante`,
    las barras son los valores de esa persona y la etapa de mayor carga es
    la suya."""
    etapas = list(cfg.etapas_analisis)
    if participante is not None:
        resultados = resultados[resultados["participante"] == participante]
    etapa, med = etapa_mayor_carga(resultados, cfg)
    fig = Figure(figsize=(9, 4.4), dpi=100, facecolor="white")
    ax = fig.subplots()
    _sombrear_etapa3(ax, etapas, cfg)
    x = np.arange(len(etapas))
    dx, ancho = 0.19, 0.36
    _limites_simetricos(ax, med[["EEG1_z", "EEG2_z"]].to_numpy().ravel().tolist(), margen=1.5)
    rng = np.random.default_rng(2)
    for (col, titulo, color), desplazamiento in zip(PANELES, (-dx, dx)):
        series = [resultados.loc[resultados["etapa"] == e, col] for e in etapas]
        _barras(ax, list(x + desplazamiento), series, color, rng, ancho=ancho, puntos=False, mostrar_ric=False)
        if participante is not None:
            _sin_datos(ax, list(x + desplazamiento), med[col].to_numpy(dtype=float))
    _ejes_etapas(ax, etapas, cfg)
    titulo = (f"Participante {participante} · comparación de etapas" if participante is not None
              else "Comparación de etapas · mediana del grupo")
    _estilo_barras(ax, titulo, flechas=False)
    ax.legend(handles=[Patch(color=COLOR_EEG1, label="EEG1 · Alfa/Theta (más bajo = más carga)"),
                       Patch(color=COLOR_EEG2, label="EEG2 · Theta (más alto = más carga)")],
              frameon=False, fontsize=8, loc="lower right", bbox_to_anchor=(1, 1.08), ncol=2,
              handlelength=1.2)
    quien = "" if participante is None else " del participante"
    if etapa is None:
        texto = [f"Etapa de mayor carga{quien}: no calculable (faltan datos)."]
    else:
        f = med.loc[etapa]
        texto = [f"Etapa de mayor carga{quien}: {etapa} ({cfg.descripcion_corta.get(etapa, '')}) · "
                 f"EEG1 {num(f['EEG1_z'])}, EEG2 {num(f['EEG2_z'])}, "
                 f"EEG2_z − EEG1_z = {num(f['diferencia'])}; {patron_carga(f['EEG1_z'], f['EEG2_z'])}."]
    pie = _pie(fig, texto, ancho_caracteres=120)
    _maquetar(fig, pie, arriba=0.97)
    return fig


# ============================================================
# Gráficos anteriores (desactivados con TIPO_GRAFICO = "barras")
# ============================================================

# ============================================================
# Líneas por participante (TIPO_GRAFICO = "lineas")
# ============================================================

def grafico_perfil(resultados: pd.DataFrame, cfg: ConfigAnalisis = ConfigAnalisis()) -> Figure:
    """Una línea gris por participante (etiquetada al final) y la mediana
    del grupo como línea gruesa de color con marcadores."""
    etapas = list(cfg.etapas_analisis)
    fig = Figure(figsize=(10, 4.2), dpi=100, facecolor="white")
    axes = fig.subplots(1, 2)
    for ax, (col, titulo, color) in zip(axes, PANELES):
        _sombrear_etapa3(ax, etapas, cfg)
        ancho = resultados.pivot_table(index="participante", columns="etapa", values=col, aggfunc="first")
        ancho = ancho.reindex(columns=etapas)
        x = np.arange(len(etapas))
        for participante, fila in ancho.iterrows():
            y = fila.to_numpy(dtype=float)
            ok = np.isfinite(y)
            if not ok.any():
                continue
            ax.plot(x[ok], y[ok], color=GRIS_CLARO, linewidth=0.9, zorder=2)
            ultimo = np.where(ok)[0][-1]
            ax.annotate(f"P{participante}", (x[ultimo], y[ultimo]), xytext=(4, 0), textcoords="offset points",
                        fontsize=7, color=GRIS, va="center")
        mediana = ancho.median()
        ax.plot(x, mediana.to_numpy(dtype=float), color=color, linewidth=2.6, marker="o", markersize=7,
                markeredgecolor="white", markeredgewidth=1.5, zorder=4, label="Mediana del grupo")
        _ejes_etapas(ax, etapas, cfg)
        ax.set_xlim(-0.5, len(etapas) - 0.2)
        _estilo(ax, titulo)
        ax.legend(frameon=False, fontsize=8, loc="lower left")
    fig.suptitle(f"Perfil por etapa (n = {resultados['participante'].nunique()} participantes)",
                 fontsize=10, color=TINTA_SUAVE, x=0.01, ha="left")
    fig.tight_layout()
    return fig


# ============================================================
# Boxplot por etapa (TIPO_GRAFICO = "boxplot")
# ============================================================

def _strip(ax, posiciones, series, color, rng, ancho=0.08):
    for x, valores in zip(posiciones, series):
        valores = np.asarray(valores, dtype=float)
        valores = valores[np.isfinite(valores)]
        jitter = rng.uniform(-ancho, ancho, size=valores.size)
        ax.scatter(np.full(valores.size, x) + jitter, valores, s=22, color=color, edgecolor="white",
                   linewidth=0.8, zorder=4, alpha=0.9)


def _boxplot(ax, posiciones, series, color, ancho=0.5):
    datos = [np.asarray(s, dtype=float)[np.isfinite(np.asarray(s, dtype=float))] for s in series]
    con_datos = [i for i, d in enumerate(datos) if d.size]
    if not con_datos:
        return
    cajas = ax.boxplot(
        [datos[i] for i in con_datos], positions=[posiciones[i] for i in con_datos], widths=ancho,
        patch_artist=True, showfliers=False, zorder=3,
        medianprops=dict(color=TINTA, linewidth=1.6),
        whiskerprops=dict(color=TINTA_SUAVE, linewidth=1), capprops=dict(color=TINTA_SUAVE, linewidth=1),
        boxprops=dict(linewidth=0),
    )
    for caja in cajas["boxes"]:
        caja.set_facecolor(color)
        caja.set_alpha(0.35)


def grafico_boxplot_etapas(resultados: pd.DataFrame, cfg: ConfigAnalisis = ConfigAnalisis()) -> Figure:
    """Distribución de las medianas z por etapa con un punto por participante."""
    etapas = list(cfg.etapas_analisis)
    rng = np.random.default_rng(0)
    fig = Figure(figsize=(10, 4.2), dpi=100, facecolor="white")
    axes = fig.subplots(1, 2)
    for ax, (col, titulo, color) in zip(axes, PANELES):
        _sombrear_etapa3(ax, etapas, cfg)
        series = [resultados.loc[resultados["etapa"] == e, col] for e in etapas]
        _boxplot(ax, list(range(len(etapas))), series, color)
        _strip(ax, list(range(len(etapas))), series, color, rng)
        _ejes_etapas(ax, etapas, cfg)
        _estilo(ax, titulo)
    fig.tight_layout()
    return fig


# ============================================================
# Boxplot agrupado alta vs baja (TIPO_GRAFICO = "boxplot" o "lineas")
# ============================================================

def grafico_alta_vs_baja(resultados: pd.DataFrame, cfg: ConfigAnalisis = ConfigAnalisis()) -> Figure:
    """Boxplot agrupado: en cada etapa con cuestionario, caja de color para
    comprensión alta (≥ mediana del puntaje de esa etapa) y gris para baja."""
    etapas = list(cfg.etapas_con_cuestionario)
    df = grupos_comprension(resultados, cfg)
    rng = np.random.default_rng(1)
    fig = Figure(figsize=(10, 4.4), dpi=100, facecolor="white")
    axes = fig.subplots(1, 2)
    x = np.arange(len(etapas))
    desplazamiento = 0.2
    for ax, (col, titulo, color) in zip(axes, PANELES):
        for grupo, dx, c in (("Comprensión alta", -desplazamiento, color), ("Comprensión baja", desplazamiento, GRIS)):
            series = [df.loc[(df["etapa"] == e) & (df["grupo"] == grupo), col] for e in etapas]
            _boxplot(ax, list(x + dx), series, c, ancho=0.32)
            _strip(ax, list(x + dx), series, c, rng, ancho=0.05)
            ax.scatter([], [], s=40, color=c, alpha=0.6, label=grupo.split()[-1].capitalize())
            for xi, s in zip(x + dx, series):
                ax.text(xi, 0.01, f"n={int(s.notna().sum())}", transform=ax.get_xaxis_transform(),
                        ha="center", va="bottom", fontsize=7, color=TINTA_SUAVE)
        _ejes_etapas(ax, etapas, cfg)
        _estilo(ax, titulo)
        ax.margins(y=0.14)
        ax.legend(frameon=False, fontsize=8, loc="lower right", bbox_to_anchor=(1, 1), ncol=2,
                  handletextpad=0.2, columnspacing=1)
    fig.suptitle("Comprensión alta (≥ mediana del puntaje de la etapa, en color) vs baja (gris)",
                 fontsize=10, color=TINTA_SUAVE, x=0.01, ha="left")
    fig.tight_layout()
    return fig


# ============================================================
# Selección según TIPO_GRAFICO
# ============================================================

def figuras_disponibles(tipo: str = TIPO_GRAFICO) -> dict:
    """clave (nombre del PNG) -> (título de la tarjeta, función)."""
    if tipo == "barras":
        return {
            "perfil_etapas": ("Figura 1 · Perfil de carga por etapa", grafico_perfil_barras),
            "comprension_alta_vs_baja": ("Figura 2 · EEG según nivel de comprensión", grafico_alta_vs_baja_barras),
            "eeg_vs_comprension": ("Figura 3 · Relación EEG–comprensión", grafico_eeg_vs_comprension),
            "resumen_etapas": ("Figura 4 · Comparación rápida de etapas", grafico_resumen_etapas),
        }
    if tipo == "boxplot":
        return {
            "boxplot_etapas": ("Distribución por etapa", grafico_boxplot_etapas),
            "eeg_vs_comprension": ("EEG vs comprensión", grafico_eeg_vs_comprension),
            "comprension_alta_vs_baja": ("Comprensión alta vs baja", grafico_alta_vs_baja),
        }
    if tipo == "lineas":
        return {
            "perfil_etapas": ("Perfil de las 4 etapas", grafico_perfil),
            "eeg_vs_comprension": ("EEG vs comprensión", grafico_eeg_vs_comprension),
            "comprension_alta_vs_baja": ("Comprensión alta vs baja", grafico_alta_vs_baja),
        }
    raise ValueError(f'TIPO_GRAFICO debe ser "barras", "boxplot" o "lineas" (no {tipo!r})')


FIGURAS = figuras_disponibles(TIPO_GRAFICO)


def _agregar_contexto(fig: Figure, contexto: str):
    """Antepone el contexto (p. ej. "Desafío 3 · Game-05") al título
    general de la figura, o al del eje si la figura no tiene uno."""
    if not contexto:
        return
    sup = fig._suptitle
    if sup is not None and sup.get_text():
        sup.set_text(f"{contexto} · {sup.get_text()}")
        return
    titulo = fig.axes[0]._left_title  # conserva tamaño y negrita
    titulo.set_text(f"{contexto} · {titulo.get_text()}")


def generar_figuras(resultados: pd.DataFrame, cfg: ConfigAnalisis = ConfigAnalisis(),
                    participante: Optional[int] = None, contexto: str = "") -> dict[str, Figure]:
    """Figuras del grupo. Con `participante`, las Figuras 1, 2 y 4 se hacen
    solo con los resultados de esa persona y la 3 (correlación, necesita a
    todo el grupo) lo marca con un anillo naranja. Los gráficos anteriores
    (TIPO_GRAFICO "boxplot"/"lineas") no tienen vista por participante.
    `contexto` (p. ej. el desafío elegido) se antepone al título de cada
    figura; `resultados` ya debe venir filtrado (ver por_desafio)."""
    figuras = {}
    for clave, (_, funcion) in FIGURAS.items():
        if participante is not None and "participante" in inspect.signature(funcion).parameters:
            figuras[clave] = funcion(resultados, cfg, participante=participante)
        else:
            figuras[clave] = funcion(resultados, cfg)
        _agregar_contexto(figuras[clave], contexto)
    return figuras


def guardar_figuras(figuras: dict[str, Figure], carpeta: Path) -> list[Path]:
    """Exporta cada figura como <clave>.png a DPI_EXPORTACION (300 dpi)."""
    carpeta.mkdir(parents=True, exist_ok=True)
    rutas = []
    for clave, fig in figuras.items():
        ruta = carpeta / f"{clave}.png"
        fig.savefig(ruta, dpi=DPI_EXPORTACION, facecolor="white", bbox_inches="tight")
        rutas.append(ruta)
    return rutas
