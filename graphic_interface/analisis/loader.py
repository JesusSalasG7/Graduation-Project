"""Lectura del dataset consolidado y exportación de la tabla de features.
Es lo único del módulo que toca disco; el cálculo vive en eeg_features.py."""

from pathlib import Path

import pandas as pd

from analisis.comprehension import attach_comprehension
from analisis.config import DATASET_FILE, FEATURES_OUT_FILE, AnalysisConfig
from analisis.eeg_features import build_feature_table


def load_dataset(path: Path = DATASET_FILE) -> pd.DataFrame:
    """Lanza FileNotFoundError con un mensaje claro si todavía no se generó
    el dataset (pestaña Sesión → "Generar dataset")."""
    if not path.exists():
        raise FileNotFoundError(
            f"No se encontró {path}. Generalo desde la pestaña Sesión o con "
            "`python data/build_dataset.py`."
        )
    return pd.read_csv(path)


def compute_features(
    path: Path = DATASET_FILE, cfg: AnalysisConfig = AnalysisConfig(),
) -> tuple[pd.DataFrame, list[str]]:
    """Dataset en disco -> tabla de features (con las columnas de
    comprensión vacías, listas para más adelante) + advertencias."""
    features, warnings = build_feature_table(load_dataset(path), cfg)
    if not features.empty:
        features = attach_comprehension(features, threshold=cfg.comprehension_threshold)
    return features, warnings


def export_features(features: pd.DataFrame, path: Path = FEATURES_OUT_FILE) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(path, index=False)
    return path
