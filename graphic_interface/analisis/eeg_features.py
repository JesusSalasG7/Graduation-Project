"""Cálculo de las features EEG de carga cognitiva (artículo "No Vibe Without
Comprehension"): EEG1 = θ/(α+β) y EEG2 = θ/α, más α/θ como control.

Todo lo de este archivo son funciones puras (entran listas/DataFrames,
salen valores nuevos, sin leer disco ni tocar la interfaz) para poder
probarlas con datos sintéticos (ver tests/test_eeg_features.py).

Unidad de análisis: una fila del dataset consolidado = participante ×
desafío × etapa × intento.
"""

import ast
import math
from typing import Any, Mapping, Optional

import numpy as np
import pandas as pd

from analisis.config import POOR_SIGNAL_NO_CONTACT, AnalysisConfig

ID_COLUMNS = ["Participante_ID", "Nivel_Experiencia", "Desafio", "Juego", "Etapa", "Intento"]

# Columnas del dataset que entran al cálculo (nombre corto -> columna).
BAND_COLUMNS = {
    "theta": "NeuroSky_Theta_List",
    "low_alpha": "NeuroSky_LowAlpha_List",
    "high_alpha": "NeuroSky_HighAlpha_List",
    "low_beta": "NeuroSky_LowBeta_List",
    "high_beta": "NeuroSky_HighBeta_List",
    "delta": "NeuroSky_Delta_List",  # solo control de artefactos
}
POOR_SIGNAL_COLUMN = "NeuroSky_PoorSignal_List"
# Métricas propietarias del chip de NeuroSky: opcionales, se reportan aparte.
ESENSE_COLUMNS = {
    "Attention": "NeuroSky_Attention_List",
    "Meditation": "NeuroSky_Meditation_List",
}

INDEX_NAMES = ["EEG1", "EEG2", "AlphaTheta"]
STAT_NAMES = {"Media": "mean", "Mediana": "median", "DE": "std", "Min": "min", "Max": "max"}

# Features agregadas que se normalizan contra la línea base y se escalan
# (z-score y Min-Max) dentro de cada participante.
NORMALIZED_FEATURES = [
    "EEG1_Media", "EEG1_Mediana",
    "EEG2_Media", "EEG2_Mediana",
    "AlphaTheta_Media", "AlphaTheta_Mediana",
    "Theta_Mediana",
]


# ============================================================
# Por muestra
# ============================================================

def parse_list(value: Any) -> list[float]:
    """Una celda "*_List" del dataset ("[1, 2, 3]") a lista de floats.
    Celda vacía, NaN o texto ilegible -> lista vacía."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return []
    if isinstance(value, (list, tuple, np.ndarray)):
        items = list(value)
    else:
        text = str(value).strip()
        if not text:
            return []
        try:
            items = ast.literal_eval(text)
        except (ValueError, SyntaxError):
            return []
        if not isinstance(items, (list, tuple)):
            return []
    out = []
    for item in items:
        try:
            out.append(float(item))
        except (TypeError, ValueError):
            out.append(float("nan"))
    return out


def align_lists(lists: Mapping[str, list[float]]) -> tuple[dict[str, np.ndarray], Optional[str]]:
    """Recorta todas las listas al largo de la más corta (las muestras se
    alinean por índice). Devuelve las listas como arrays y una advertencia
    si había largos distintos."""
    lengths = {name: len(values) for name, values in lists.items()}
    shortest = min(lengths.values()) if lengths else 0
    warning = None
    if len(set(lengths.values())) > 1:
        detail = ", ".join(f"{name}={n}" for name, n in lengths.items())
        warning = f"Listas de largo distinto ({detail}); se recortaron a {shortest} muestras."
    aligned = {name: np.asarray(values[:shortest], dtype=float) for name, values in lists.items()}
    return aligned, warning


def quality_mask(poor_signal: np.ndarray, threshold: int = 0) -> np.ndarray:
    """True en las muestras que se conservan: PoorSignal <= umbral y nunca
    las de 200 (electrodo sin contacto), aunque el umbral sea mayor."""
    poor_signal = np.asarray(poor_signal, dtype=float)
    return (poor_signal <= threshold) & (poor_signal != POOR_SIGNAL_NO_CONTACT)


def combine_bands(
    low_alpha: np.ndarray, high_alpha: np.ndarray, low_beta: np.ndarray, high_beta: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """α = LowAlpha + HighAlpha, β = LowBeta + HighBeta (por muestra)."""
    alpha = np.asarray(low_alpha, dtype=float) + np.asarray(high_alpha, dtype=float)
    beta = np.asarray(low_beta, dtype=float) + np.asarray(high_beta, dtype=float)
    return alpha, beta


def log_transform(values: np.ndarray) -> np.ndarray:
    """log(x + 1). Las potencias de NeuroSky no son negativas; si llegara
    alguna, se lleva a 0 para no producir -inf."""
    return np.log1p(np.clip(np.asarray(values, dtype=float), 0, None))


def safe_ratio(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    """numerador / denominador, con NaN donde el denominador es 0 o NaN."""
    numerator = np.asarray(numerator, dtype=float)
    denominator = np.asarray(denominator, dtype=float)
    out = np.full(np.broadcast(numerator, denominator).shape, np.nan)
    ok = np.isfinite(denominator) & (denominator != 0)
    np.divide(numerator, denominator, out=out, where=ok)
    return out


def cognitive_indices(theta: np.ndarray, alpha: np.ndarray, beta: np.ndarray) -> dict[str, np.ndarray]:
    """Índices por muestra, sobre las bandas YA transformadas con log:
    EEG1 = θ/(α+β) (esfuerzo mental / control atencional),
    EEG2 = θ/α (carga de memoria de trabajo), AlphaTheta = α/θ."""
    return {
        "EEG1": safe_ratio(theta, np.asarray(alpha, dtype=float) + np.asarray(beta, dtype=float)),
        "EEG2": safe_ratio(theta, alpha),
        "AlphaTheta": safe_ratio(alpha, theta),
    }


def summarize(values: np.ndarray) -> dict[str, float]:
    """Media, mediana, desviación estándar (muestral, ddof=1), mínimo y
    máximo, ignorando NaN. Sin valores -> todo NaN."""
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return {name: float("nan") for name in STAT_NAMES}
    return {
        "Media": float(np.mean(values)),
        "Mediana": float(np.median(values)),
        "DE": float(np.std(values, ddof=1)) if values.size > 1 else float("nan"),
        "Min": float(np.min(values)),
        "Max": float(np.max(values)),
    }


# ============================================================
# Por etapa (una fila del dataset)
# ============================================================

def _empty_stage_features() -> dict:
    out = {f"{index}_{stat}": float("nan") for index in INDEX_NAMES for stat in STAT_NAMES}
    out.update({"Theta_Mediana": float("nan"), "Delta_Media": float("nan")})
    return out


def process_stage(row: Mapping[str, Any], cfg: AnalysisConfig = AnalysisConfig()) -> dict:
    """Features de una etapa a partir de las columnas NeuroSky_*_List de su
    fila. Nunca lanza: una etapa sin datos sale marcada como "datos
    insuficientes" con las features en NaN."""
    warnings: list[str] = []
    out: dict = {}

    raw = {name: parse_list(row.get(col)) for name, col in BAND_COLUMNS.items()}
    raw["poor_signal"] = parse_list(row.get(POOR_SIGNAL_COLUMN))
    esense_raw = {name: parse_list(row.get(col)) for name, col in ESENSE_COLUMNS.items()}
    esense_raw = {name: values for name, values in esense_raw.items() if values}

    if any(len(values) == 0 for values in raw.values()):
        missing = [BAND_COLUMNS.get(name, POOR_SIGNAL_COLUMN) for name, values in raw.items() if not values]
        out.update(_empty_stage_features())
        out.update({
            "Muestras_Totales": 0, "Muestras_Validas": 0, "Pct_Descartado": float("nan"),
            "Datos_Insuficientes": True,
            "Advertencias": "Sin datos NeuroSky en: " + ", ".join(missing),
        })
        out.update(_esense_features({}, None))
        return out

    aligned, length_warning = align_lists({**raw, **esense_raw})
    if length_warning:
        warnings.append(length_warning)

    mask = quality_mask(aligned["poor_signal"], cfg.poor_signal_threshold)
    total = int(mask.size)
    valid = int(mask.sum())
    out["Muestras_Totales"] = total
    out["Muestras_Validas"] = valid
    out["Pct_Descartado"] = round(100.0 * (total - valid) / total, 2) if total else float("nan")
    insufficient = valid < cfg.min_valid_samples or (total > 0 and valid / total < cfg.min_valid_fraction)
    out["Datos_Insuficientes"] = bool(insufficient)
    if insufficient:
        warnings.append(f"Datos insuficientes: {valid} de {total} muestras válidas.")

    alpha_raw, beta_raw = combine_bands(
        aligned["low_alpha"][mask], aligned["high_alpha"][mask],
        aligned["low_beta"][mask], aligned["high_beta"][mask],
    )
    theta = log_transform(aligned["theta"][mask])
    alpha = log_transform(alpha_raw)
    beta = log_transform(beta_raw)
    delta = log_transform(aligned["delta"][mask])

    for index, values in cognitive_indices(theta, alpha, beta).items():
        for stat, value in summarize(values).items():
            out[f"{index}_{stat}"] = value
    out["Theta_Mediana"] = float(np.median(theta)) if theta.size else float("nan")
    out["Delta_Media"] = float(np.mean(delta)) if delta.size else float("nan")

    out.update(_esense_features({name: aligned[name] for name in esense_raw}, mask))
    out["Advertencias"] = " ".join(warnings)
    return out


def _esense_features(esense: Mapping[str, np.ndarray], mask: Optional[np.ndarray]) -> dict:
    """Media y mediana de Attention/Meditation (eSense, propietario
    NeuroSky) sobre las muestras válidas. Un 0 de eSense significa que el
    chip todavía no pudo calcular el valor, así que también se descarta."""
    out = {}
    for name in ESENSE_COLUMNS:
        values = esense.get(name)
        if values is None or mask is None:
            out[f"eSense_{name}_Media"] = float("nan")
            out[f"eSense_{name}_Mediana"] = float("nan")
            continue
        kept = values[mask]
        kept = kept[np.isfinite(kept) & (kept > 0)]
        out[f"eSense_{name}_Media"] = float(np.mean(kept)) if kept.size else float("nan")
        out[f"eSense_{name}_Mediana"] = float(np.median(kept)) if kept.size else float("nan")
    return out


# ============================================================
# Por tabla (normalizaciones entre filas)
# ============================================================

def baseline_change_pct(value: float, base: float) -> float:
    """(valor_etapa − valor_base) / valor_base × 100; NaN si la base es 0
    o falta alguno de los dos valores."""
    if value is None or base is None or not np.isfinite(value) or not np.isfinite(base) or base == 0:
        return float("nan")
    return (value - base) / base * 100.0


def add_baseline_change(
    features: pd.DataFrame, cfg: AnalysisConfig = AnalysisConfig(),
    columns: list[str] = NORMALIZED_FEATURES,
) -> tuple[pd.DataFrame, list[str]]:
    """Agrega "<feature>_Cambio_Pct" respecto a la etapa de línea base
    (cfg.baseline_stage) del MISMO participante y desafío. Si esa etapa
    tiene varios intentos se usa el primero. Sin línea base válida (no
    existe o tiene datos insuficientes) las columnas quedan en NaN,
    Linea_Base_Disponible = False y se devuelve una advertencia."""
    df = features.copy()
    warnings: list[str] = []
    for col in columns:
        df[f"{col}_Cambio_Pct"] = np.nan
    df["Linea_Base_Disponible"] = False

    for (participant, challenge), group in df.groupby(["Participante_ID", "Desafio"], sort=True):
        candidates = group[(group["Etapa"] == cfg.baseline_stage) & (~group["Datos_Insuficientes"].astype(bool))]
        if candidates.empty:
            warnings.append(
                f"Participante {participant}, desafío {challenge}: sin línea base válida "
                f"(Etapa {cfg.baseline_stage}); no se calculó el cambio %."
            )
            continue
        base = candidates.sort_values("Intento").iloc[0]
        for idx, row in group.iterrows():
            if bool(row["Datos_Insuficientes"]):
                continue
            df.at[idx, "Linea_Base_Disponible"] = True
            for col in columns:
                df.at[idx, f"{col}_Cambio_Pct"] = baseline_change_pct(row[col], base[col])
    return df, warnings


def _zscore(values: pd.Series) -> pd.Series:
    std = values.std(ddof=0)
    if values.count() == 0:
        return values * np.nan
    if not np.isfinite(std) or std == 0:
        return values.where(values.isna(), 0.0)
    return (values - values.mean()) / std


def _minmax(values: pd.Series) -> pd.Series:
    low, high = values.min(), values.max()
    if values.count() == 0:
        return values * np.nan
    if high == low:
        return values.where(values.isna(), 0.0)
    return (values - low) / (high - low)


def add_within_participant_scaling(
    features: pd.DataFrame, columns: list[str] = NORMALIZED_FEATURES,
) -> pd.DataFrame:
    """Agrega "<feature>_Z" (z-score, ddof=0) y "<feature>_MinMax" (0–1),
    calculados dentro de cada participante y solo con sus etapas con datos
    suficientes (las demás quedan en NaN). Si todas sus etapas valen lo
    mismo, ambos dan 0."""
    df = features.copy()
    valid = ~df["Datos_Insuficientes"].astype(bool)
    for col in columns:
        df[f"{col}_Z"] = np.nan
        df[f"{col}_MinMax"] = np.nan
        for _, idx in df[valid].groupby("Participante_ID").groups.items():
            values = df.loc[idx, col].astype(float)
            df.loc[idx, f"{col}_Z"] = _zscore(values)
            df.loc[idx, f"{col}_MinMax"] = _minmax(values)
    return df


def flag_delta_artifacts(features: pd.DataFrame, z_threshold: float) -> pd.DataFrame:
    """Delta_Media_Z (z-score de la media de log(δ) dentro del participante)
    y Delta_Atipica = True cuando supera z_threshold: posibles parpadeos o
    movimientos (NeuroSky mide en Fp1, sobre la frente)."""
    df = features.copy()
    df["Delta_Media_Z"] = np.nan
    valid = ~df["Datos_Insuficientes"].astype(bool)
    for _, idx in df[valid].groupby("Participante_ID").groups.items():
        df.loc[idx, "Delta_Media_Z"] = _zscore(df.loc[idx, "Delta_Media"].astype(float))
    df["Delta_Atipica"] = df["Delta_Media_Z"] > z_threshold
    return df


def build_feature_table(
    dataset: pd.DataFrame, cfg: AnalysisConfig = AnalysisConfig(),
) -> tuple[pd.DataFrame, list[str]]:
    """Pipeline completo sobre el dataset consolidado: una fila de features
    por fila del dataset. Devuelve la tabla y las advertencias globales
    (las de cada etapa quedan en su columna "Advertencias")."""
    rows = []
    for _, row in dataset.iterrows():
        ids = {col: row.get(col) for col in ID_COLUMNS}
        rows.append({**ids, **process_stage(row, cfg)})
    features = pd.DataFrame(rows)
    if features.empty:
        return features, ["El dataset no tiene filas."]

    features, warnings = add_baseline_change(features, cfg)
    features = add_within_participant_scaling(features)
    features = flag_delta_artifacts(features, cfg.delta_alert_z)
    return features, warnings
