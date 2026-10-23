"""Pipeline de procesamiento EEG: del dataset consolidado a una tabla con
un valor por participante y etapa de los indicadores EEG1 (Alfa/Theta) y
EEG2 (Theta), normalizados dentro de cada participante.

Replica la metodología del artículo de referencia con un NeuroSky de un
solo canal frontal (Fp1). Todas las funciones son puras (DataFrame entra,
DataFrame sale, sin leer disco ni tocar la interfaz), salvo cargar_dataset,
para poder probarlas con datos sintéticos (ver tests/test_pipeline.py).

Orden de los pasos (ejecutar_pipeline):
    1. cargar_dataset + expandir_formato_largo
    2. filtrar_calidad (+ reporte de calidad)
    3. calcular_indicadores
    4. transformar_log
    5. normalizar_por_participante
    6. agregar_por_etapa
    7. unir_puntajes
"""

import ast
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from analisis.config import RUTA_DATASET, ConfigAnalisis

# ------------------------------------------------------------------
# Columnas de dataset_sesiones.csv
# ------------------------------------------------------------------
COL_PARTICIPANTE = "Participante_ID"
COL_ETAPA = "Etapa"
COL_DESAFIO = "Desafio"
COL_INTENTO = "Intento"
COL_DURACION = "Duracion_Segundos"
COL_INICIO = "Hora_Inicio"
COL_FIN = "Hora_Fin"
COL_CORRECTAS = "Cuestionario_Correctas"
COL_TOTAL_PREGUNTAS = "Cuestionario_Total"

# Listas por segundo (nombre corto en formato largo -> columna del CSV).
COLUMNAS_LISTA = {
    "theta": "NeuroSky_Theta_List",
    "low_alpha": "NeuroSky_LowAlpha_List",
    "high_alpha": "NeuroSky_HighAlpha_List",
    "low_beta": "NeuroSky_LowBeta_List",
    "high_beta": "NeuroSky_HighBeta_List",
    "delta": "NeuroSky_Delta_List",  # solo control de artefactos
    "poor_signal": "NeuroSky_PoorSignal_List",
    "attention": "NeuroSky_Attention_List",  # complementaria (eSense)
    "meditation": "NeuroSky_Meditation_List",  # complementaria (eSense)
}
# Gamma (LowGamma/MidGamma) no se lee: en Fp1 está dominada por ruido muscular.

INDICADORES = ["EEG1", "EEG2"]
INDICADORES_OPCIONALES = ["theta_beta", "engagement"]
TODOS_INDICADORES = INDICADORES + INDICADORES_OPCIONALES
COLUMNAS_Z = [f"{ind}_z" for ind in TODOS_INDICADORES]

COLUMNAS_RESULTADO = [
    "participante", "etapa", *COLUMNAS_Z,
    "duracion_s", "attention_prom", "meditation_prom", "puntaje", "pct_muestras_validas",
]


@dataclass
class ResultadoPipeline:
    resultados: pd.DataFrame  # una fila por participante y etapa (COLUMNAS_RESULTADO)
    calidad: pd.DataFrame  # reporte de calidad por participante y etapa
    muestras: pd.DataFrame  # muestras válidas con indicadores, log y z
    avisos: list[str] = field(default_factory=list)
    etapas_ignoradas: list[str] = field(default_factory=list)  # etapas del CSV fuera del análisis


# ============================================================
# Utilidades
# ============================================================

def normalizar_etapa(valor: Any) -> Optional[str]:
    """Lleva cualquier forma de escribir la etapa ("2", 2, 2.0, "etapa_2",
    "Etapa 2") al nombre canónico "Etapa N", que es el que se usa en todo
    el código, las tablas y los gráficos. Sin número reconocible -> None."""
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return None
    if isinstance(valor, (int, np.integer)) or (isinstance(valor, float) and float(valor).is_integer()):
        return f"Etapa {int(valor)}"
    coincidencia = re.search(r"(\d+)", str(valor))
    return f"Etapa {int(coincidencia.group(1))}" if coincidencia else None


def parsear_lista(valor: Any) -> list[float]:
    """Convierte una celda *_List del CSV a lista de números.

    En dataset_sesiones.csv las listas se guardan como texto con forma de
    lista de Python ("[1, 2, 3]"); también se aceptan valores separados por
    comas o punto y coma sin corchetes. Celda vacía o ilegible -> [].
    """
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return []
    if isinstance(valor, (list, tuple, np.ndarray)):
        elementos = list(valor)
    else:
        texto = str(valor).strip()
        if not texto:
            return []
        try:
            elementos = ast.literal_eval(texto)
            if not isinstance(elementos, (list, tuple)):
                elementos = [elementos]
        except (ValueError, SyntaxError):
            elementos = [p for p in re.split(r"[;,\s]+", texto.strip("[]()")) if p]
    salida = []
    for e in elementos:
        try:
            salida.append(float(e))
        except (TypeError, ValueError):
            salida.append(float("nan"))
    return salida


def interpretar_carga(eeg1_z: float, eeg2_z: float) -> str:
    """Regla de interpretación conjunta (valores relativos al participante):
    alta carga = EEG1_z < 0 (menos alfa respecto de theta) y EEG2_z > 0
    (más theta, memoria de trabajo); baja carga = el patrón inverso. Si los
    dos indicadores se contradicen, el resultado es no concluyente."""
    if eeg1_z is None or eeg2_z is None or not np.isfinite(eeg1_z) or not np.isfinite(eeg2_z):
        return "Sin datos"
    if eeg1_z < 0 and eeg2_z > 0:
        return "Alta carga"
    if eeg1_z > 0 and eeg2_z < 0:
        return "Baja carga"
    return "No concluyente"


# ============================================================
# Paso 1: cargar y expandir
# ============================================================

def cargar_dataset(ruta: Path = RUTA_DATASET) -> pd.DataFrame:
    """Lee dataset_sesiones.csv. Lanza FileNotFoundError con un mensaje
    claro si todavía no se generó (pestaña Sesión → "Generar dataset")."""
    ruta = Path(ruta)
    if not ruta.exists():
        raise FileNotFoundError(
            f"No se encontró {ruta}. Generalo desde la pestaña Sesión o con "
            "`python data/build_dataset.py`."
        )
    return pd.read_csv(ruta)


def etapas_presentes(dataset: pd.DataFrame) -> list[str]:
    """Nombres canónicos de todas las etapas que aparecen en el dataset."""
    etapas = {normalizar_etapa(v) for v in dataset[COL_ETAPA].unique()}
    return sorted((e for e in etapas if e), key=lambda e: int(e.split()[-1]))


def expandir_formato_largo(
    dataset: pd.DataFrame, cfg: ConfigAnalisis = ConfigAnalisis(),
) -> tuple[pd.DataFrame, list[str]]:
    """Filtra las etapas del análisis (y la de línea base, si se configuró)
    y expande cada fila del dataset a una fila por segundo.

    Por qué: las columnas *_List guardan la serie de toda la etapa
    (~1 muestra/s) alineada por índice; para filtrar la calidad y
    normalizar muestra a muestra hace falta tenerlas en formato largo. Si
    las listas de una fila tienen largos distintos se recortan al mínimo
    (las muestras se alinean por posición) y se avisa.

    Cada fila del dataset es participante × desafío × etapa × intento; en
    formato largo se conservan desafío e intento, pero el resto del
    pipeline junta todas las muestras de un participante en cada etapa.
    """
    etapas = list(cfg.etapas_analisis)
    if cfg.etapa_linea_base and cfg.etapa_linea_base not in etapas:
        etapas.append(cfg.etapa_linea_base)

    avisos: list[str] = []
    bloques = []
    for _, fila in dataset.iterrows():
        etapa = normalizar_etapa(fila[COL_ETAPA])
        if etapa not in etapas:
            continue
        listas = {nombre: parsear_lista(fila.get(col)) for nombre, col in COLUMNAS_LISTA.items()}
        largos = {nombre: len(v) for nombre, v in listas.items()}
        n = min(largos.values())
        ident = (
            f"P{fila[COL_PARTICIPANTE]} · {etapa} · desafío {fila.get(COL_DESAFIO, '—')} · "
            f"intento {fila.get(COL_INTENTO, '—')}"
        )
        if len(set(largos.values())) > 1:
            detalle = ", ".join(f"{k}={v}" for k, v in largos.items())
            avisos.append(f"{ident}: listas de largo distinto ({detalle}); recortadas a {n}.")
        if n == 0:
            avisos.append(f"{ident}: sin muestras de NeuroSky.")
            continue
        bloque = pd.DataFrame({nombre: np.asarray(v[:n], dtype=float) for nombre, v in listas.items()})
        bloque.insert(0, "segundo", np.arange(n))
        bloque.insert(0, "intento", fila.get(COL_INTENTO, 1))
        bloque.insert(0, "desafio", fila.get(COL_DESAFIO, 1))
        bloque.insert(0, "etapa", etapa)
        bloque.insert(0, "participante", fila[COL_PARTICIPANTE])
        bloques.append(bloque)

    columnas = ["participante", "etapa", "desafio", "intento", "segundo", *COLUMNAS_LISTA]
    largo = pd.concat(bloques, ignore_index=True) if bloques else pd.DataFrame(columns=columnas)
    return largo, avisos


# ============================================================
# Paso 2: control de calidad
# ============================================================

def marcar_muestras_validas(largo: pd.DataFrame, cfg: ConfigAnalisis = ConfigAnalisis()) -> pd.Series:
    """True en las muestras que se conservan.

    Por qué: con mal contacto del electrodo (PoorSignal > 0) las potencias
    de banda son ruido, y con Theta o Alfa <= 0 el cociente y el logaritmo
    no están definidos. Se exige PoorSignal <= UMBRAL_POOR_SIGNAL (por
    defecto 0, es decir, señal perfecta)."""
    alfa = largo["low_alpha"] + largo["high_alpha"]
    return (
        (largo["poor_signal"] <= cfg.umbral_poor_signal)
        & (largo["theta"] > 0)
        & (alfa > 0)
    ).fillna(False)


def reporte_calidad(largo: pd.DataFrame, cfg: ConfigAnalisis = ConfigAnalisis()) -> pd.DataFrame:
    """Por participante y etapa: muestras totales, válidas, % válido y la
    marca de "baja calidad" (< MIN_PCT_VALIDO % o < MIN_MUESTRAS_VALIDAS
    válidas). Incluye además, como control de artefactos, el % de muestras
    válidas con Delta alta (log Delta > media + DELTA_Z_ARTEFACTO·DE del
    participante): en Fp1 los parpadeos y movimientos inflan Delta. Delta
    NO se usa como indicador de carga."""
    df = largo.copy()
    df["valida"] = marcar_muestras_validas(df, cfg)
    log_delta = np.log(df["delta"].where(df["delta"] > 0))
    ref = log_delta.where(df["valida"]).groupby(df["participante"]).agg(["mean", "std"])
    umbral = df["participante"].map(ref["mean"] + cfg.delta_z_artefacto * ref["std"])
    df["delta_alta"] = df["valida"] & (log_delta > umbral)

    g = df.groupby(["participante", "etapa"], sort=True)
    calidad = pd.DataFrame({
        "muestras_totales": g.size(),
        "muestras_validas": g["valida"].sum().astype(int),
        "n_delta_alta": g["delta_alta"].sum().astype(int),
    }).reset_index()
    calidad["pct_valido"] = 100.0 * calidad["muestras_validas"] / calidad["muestras_totales"]
    calidad["pct_delta_alta"] = np.where(
        calidad["muestras_validas"] > 0,
        100.0 * calidad["n_delta_alta"] / calidad["muestras_validas"].replace(0, np.nan),
        np.nan,
    )
    calidad["baja_calidad"] = (
        (calidad["pct_valido"] < cfg.min_pct_valido)
        | (calidad["muestras_validas"] < cfg.min_muestras_validas)
    )
    return calidad.drop(columns="n_delta_alta")


def filtrar_calidad(
    largo: pd.DataFrame, cfg: ConfigAnalisis = ConfigAnalisis(),
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Aplica el control de calidad: deja solo las muestras válidas y, si
    EXCLUIR_BAJA_CALIDAD, quita las etapas marcadas como baja calidad
    (antes de normalizar, para que no contaminen la media y la DE del
    participante). Devuelve (muestras válidas, reporte, avisos)."""
    calidad = reporte_calidad(largo, cfg)
    avisos = []
    validas = largo[marcar_muestras_validas(largo, cfg)].copy()
    bajas = calidad[calidad["baja_calidad"]]
    for _, r in bajas.iterrows():
        accion = "excluida" if cfg.excluir_baja_calidad else "conservada"
        avisos.append(
            f"P{r['participante']} · {r['etapa']}: baja calidad ({int(r['muestras_validas'])} válidas, "
            f"{r['pct_valido']:.1f} %), {accion}."
        )
    if cfg.excluir_baja_calidad and not bajas.empty:
        claves = set(zip(bajas["participante"], bajas["etapa"]))
        fuera = [(p, e) in claves for p, e in zip(validas["participante"], validas["etapa"])]
        validas = validas[~np.asarray(fuera, dtype=bool)]
    return validas.reset_index(drop=True), calidad, avisos


# ============================================================
# Pasos 3 y 4: indicadores y logaritmo
# ============================================================

def calcular_indicadores(muestras: pd.DataFrame) -> pd.DataFrame:
    """Indicadores por muestra (segundo):

    - alpha = LowAlpha + HighAlpha (NeuroSky divide alfa en dos sub-bandas).
    - EEG1 = alpha / Theta: el cociente baja cuando aumenta la carga
      cognitiva (alfa se suprime y theta frontal crece).
    - EEG2 = Theta: la potencia theta frontal crece con la demanda de
      memoria de trabajo.
    - Opcionales (no principales): theta_beta = Theta / (LowBeta +
      HighBeta) y engagement = beta / (alpha + Theta).

    Un denominador <= 0 deja el indicador opcional en NaN.
    """
    df = muestras.copy()
    df["alpha"] = df["low_alpha"] + df["high_alpha"]
    df["beta"] = df["low_beta"] + df["high_beta"]
    df["EEG1"] = df["alpha"] / df["theta"]
    df["EEG2"] = df["theta"]
    df["theta_beta"] = df["theta"] / df["beta"].where(df["beta"] > 0)
    df["engagement"] = df["beta"] / (df["alpha"] + df["theta"])
    return df


def transformar_log(muestras: pd.DataFrame) -> pd.DataFrame:
    """Logaritmo natural de cada indicador (columnas ln_<indicador>).

    Por qué: las potencias de NeuroSky varían varios órdenes de magnitud y
    tienen una distribución muy sesgada a la derecha; el log la acerca a
    una normal y evita que unos pocos picos dominen la media y la DE que se
    usan para normalizar. Valores <= 0 quedan en NaN."""
    df = muestras.copy()
    for ind in TODOS_INDICADORES:
        df[f"ln_{ind}"] = np.log(df[ind].where(df[ind] > 0))
    return df


# ============================================================
# Paso 5: normalización z por participante
# ============================================================

def normalizar_por_participante(
    muestras: pd.DataFrame, cfg: ConfigAnalisis = ConfigAnalisis(),
) -> tuple[pd.DataFrame, list[str]]:
    """z = (x − media) / DE de cada indicador logarítmico, con la media y
    la DE (muestral, ddof = 1) de CADA participante.

    Por qué: la potencia absoluta del EEG depende de factores ajenos a la
    tarea (grosor del cráneo, impedancia, colocación del electrodo), así
    que solo es comparable dentro de la misma persona. z = 0 es el nivel
    habitual del participante y los valores son relativos a él.

    Referencia: sin ETAPA_LINEA_BASE, todas sus muestras válidas de las
    etapas del análisis juntas; con ETAPA_LINEA_BASE, solo las de esa
    etapa (que luego se quita de los resultados).
    """
    df = muestras.copy()
    avisos: list[str] = []
    base = cfg.etapa_linea_base
    ref = df[df["etapa"] == base] if base else df[df["etapa"].isin(cfg.etapas_analisis)]
    columnas_ln = [f"ln_{ind}" for ind in TODOS_INDICADORES]
    stats = ref.groupby("participante")[columnas_ln].agg(["mean", "std"])

    for ind in TODOS_INDICADORES:
        col = f"ln_{ind}"
        media = df["participante"].map(stats[(col, "mean")]) if not stats.empty else np.nan
        desv = df["participante"].map(stats[(col, "std")]) if not stats.empty else np.nan
        desv = desv.where(desv > 0) if isinstance(desv, pd.Series) else desv
        df[f"{ind}_z"] = (df[col] - media) / desv

    sin_ref = sorted(set(df["participante"]) - set(stats.index))
    for p in sin_ref:
        avisos.append(
            f"P{p}: sin muestras de referencia "
            f"({base or 'etapas del análisis'}); sus z quedan vacíos."
        )
    if base:
        df = df[df["etapa"] != base]
    return df.reset_index(drop=True), avisos


# ============================================================
# Paso 6 y 7: agregar por etapa y unir puntajes
# ============================================================

def _duracion_por_etapa(dataset: pd.DataFrame) -> pd.Series:
    """Duración (s) de cada fila del dataset: Duracion_Segundos o, si
    falta, Hora_Fin − Hora_Inicio."""
    dur = pd.to_numeric(dataset.get(COL_DURACION), errors="coerce") if COL_DURACION in dataset else None
    if dur is None:
        dur = pd.Series(np.nan, index=dataset.index)
    if COL_INICIO in dataset and COL_FIN in dataset:
        calculada = (
            pd.to_datetime(dataset[COL_FIN], errors="coerce") - pd.to_datetime(dataset[COL_INICIO], errors="coerce")
        ).dt.total_seconds()
        dur = dur.fillna(calculada)
    return dur


def agregar_por_etapa(
    muestras: pd.DataFrame, calidad: pd.DataFrame, dataset: pd.DataFrame,
    cfg: ConfigAnalisis = ConfigAnalisis(),
) -> pd.DataFrame:
    """Una fila por participante y etapa con la MEDIANA de los z.

    Por qué la mediana: es robusta a los segundos con artefactos que
    sobreviven al filtro de PoorSignal. Todos los desafíos e intentos de
    la misma etapa se juntan en una sola serie por participante.

    Complementarias: duración total de la etapa (suma de Duracion_Segundos
    de sus filas; si no hay tiempos, el número de muestras, ~1/s),
    Attention y Meditation promedio sobre las muestras válidas (se ignoran
    los 0, que indican que el chip aún no había calculado el eSense) y el
    % de muestras válidas del reporte de calidad. Attention y Meditation
    son algoritmos propietarios: NO sustituyen a EEG1 ni EEG2.
    """
    claves = ["participante", "etapa"]
    if muestras.empty:
        return pd.DataFrame(columns=[c for c in COLUMNAS_RESULTADO if c != "puntaje"])
    g = muestras.groupby(claves, sort=True)
    agregado = g[COLUMNAS_Z].median()
    agregado["attention_prom"] = g["attention"].apply(lambda s: s[s > 0].mean())
    agregado["meditation_prom"] = g["meditation"].apply(lambda s: s[s > 0].mean())
    agregado["n_muestras"] = g.size()
    agregado = agregado.reset_index()

    ds = dataset.copy()
    ds["participante"] = ds[COL_PARTICIPANTE]
    ds["etapa"] = ds[COL_ETAPA].map(normalizar_etapa)
    ds["_dur"] = _duracion_por_etapa(ds)
    duracion = ds.groupby(claves)["_dur"].sum(min_count=1).rename("duracion_s").reset_index()
    agregado = agregado.merge(duracion, on=claves, how="left")
    agregado["duracion_s"] = agregado["duracion_s"].fillna(agregado["n_muestras"].astype(float))

    agregado = agregado.merge(
        calidad[claves + ["pct_valido"]].rename(columns={"pct_valido": "pct_muestras_validas"}),
        on=claves, how="left",
    )
    return agregado.drop(columns="n_muestras")


def puntajes_por_etapa(dataset: pd.DataFrame, cfg: ConfigAnalisis = ConfigAnalisis()) -> pd.DataFrame:
    """% de aciertos por participante y etapa con cuestionario: suma de
    Cuestionario_Correctas / suma de Cuestionario_Total × 100 sobre todos
    sus desafíos e intentos. Solo se usan filas con ambos valores."""
    ds = dataset[[COL_PARTICIPANTE, COL_ETAPA, COL_CORRECTAS, COL_TOTAL_PREGUNTAS]].copy()
    ds.columns = ["participante", "etapa", "correctas", "total"]
    ds["etapa"] = ds["etapa"].map(normalizar_etapa)
    ds = ds[ds["etapa"].isin(cfg.etapas_con_cuestionario)].dropna(subset=["correctas", "total"])
    ds = ds[ds["total"] > 0]
    g = ds.groupby(["participante", "etapa"])[["correctas", "total"]].sum()
    return (100.0 * g["correctas"] / g["total"]).rename("puntaje").reset_index()


def unir_puntajes(
    agregado: pd.DataFrame, dataset: pd.DataFrame, cfg: ConfigAnalisis = ConfigAnalisis(),
) -> pd.DataFrame:
    """Agrega la columna puntaje (% de aciertos). La etapa sin cuestionario
    (Etapa 3) queda en NaN por definición."""
    df = agregado.merge(puntajes_por_etapa(dataset, cfg), on=["participante", "etapa"], how="left")
    df.loc[df["etapa"] == cfg.etapa_sin_cuestionario, "puntaje"] = np.nan
    orden = {e: i for i, e in enumerate(cfg.etapas_analisis)}
    df = df.sort_values(["participante", "etapa"], key=lambda s: s.map(orden) if s.name == "etapa" else s)
    return df[COLUMNAS_RESULTADO].reset_index(drop=True)


# ============================================================
# Pipeline completo
# ============================================================

def ejecutar_pipeline(dataset: pd.DataFrame, cfg: ConfigAnalisis = ConfigAnalisis()) -> ResultadoPipeline:
    """Pasos 1–7 en orden sobre el dataset ya leído."""
    avisos: list[str] = []
    presentes = etapas_presentes(dataset)
    usadas = set(cfg.etapas_analisis) | ({cfg.etapa_linea_base} if cfg.etapa_linea_base else set())
    ignoradas = [e for e in presentes if e not in usadas]
    if cfg.etapa_linea_base and cfg.etapa_linea_base not in presentes:
        avisos.append(f"La etapa de línea base ({cfg.etapa_linea_base}) no está en el dataset.")

    largo, av = expandir_formato_largo(dataset, cfg)
    avisos += av
    if largo.empty:
        vacio = pd.DataFrame(columns=COLUMNAS_RESULTADO)
        return ResultadoPipeline(vacio, pd.DataFrame(), largo, avisos + ["No hay muestras de NeuroSky."], ignoradas)

    validas, calidad, av = filtrar_calidad(largo, cfg)
    avisos += av
    muestras = transformar_log(calcular_indicadores(validas))
    muestras, av = normalizar_por_participante(muestras, cfg)
    avisos += av
    calidad = calidad[calidad["etapa"].isin(cfg.etapas_analisis)].reset_index(drop=True)
    agregado = agregar_por_etapa(muestras, calidad, dataset, cfg)
    resultados = unir_puntajes(agregado, dataset, cfg)
    return ResultadoPipeline(resultados, calidad, muestras, avisos, ignoradas)
