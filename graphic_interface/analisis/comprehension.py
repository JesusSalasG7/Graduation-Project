"""Punto de extensión para la puntuación de comprensión (0–6) y los
clasificadores que se conectarán más adelante. Todavía NO entrena ni
predice nada: solo deja las columnas y las funciones listas.

Las columnas que agrega a la tabla de features:
- Comprension_Puntaje: la puntuación 0–6 (NaN mientras no se cargue).
- Comprension_Alta: True si puntaje > umbral (por defecto 3.5), False si
  no, vacío si no hay puntaje.
"""

from typing import Mapping, Optional, Protocol

import numpy as np
import pandas as pd

from analisis.config import COMPREHENSION_MAX, COMPREHENSION_MIN, COMPREHENSION_THRESHOLD

# Clave de cada puntuación: la misma unidad de análisis que la tabla.
ScoreKey = tuple[int, int, int, int]  # (Participante_ID, Desafio, Etapa, Intento)
KEY_COLUMNS = ["Participante_ID", "Desafio", "Etapa", "Intento"]


def binarize_comprehension(score: Optional[float], threshold: float = COMPREHENSION_THRESHOLD) -> Optional[bool]:
    """Puntaje 0–6 -> True (comprensión alta) / False (baja); None si falta.
    Lanza ValueError si el puntaje está fuera de 0–6."""
    if score is None or (isinstance(score, float) and np.isnan(score)):
        return None
    if not COMPREHENSION_MIN <= score <= COMPREHENSION_MAX:
        raise ValueError(f"Puntaje de comprensión fuera de rango (0–6): {score}")
    return bool(score > threshold)


def attach_comprehension(
    features: pd.DataFrame,
    scores: Optional[Mapping[ScoreKey, float]] = None,
    threshold: float = COMPREHENSION_THRESHOLD,
) -> pd.DataFrame:
    """Agrega Comprension_Puntaje y Comprension_Alta. Sin `scores` (hoy)
    ambas quedan vacías; más adelante se pasa un dict
    {(participante, desafío, etapa, intento): puntaje}."""
    df = features.copy()
    scores = scores or {}
    keys = df[KEY_COLUMNS].astype(int).itertuples(index=False, name=None)
    df["Comprension_Puntaje"] = [scores.get(tuple(key), np.nan) for key in keys]
    df["Comprension_Alta"] = [
        binarize_comprehension(score, threshold) for score in df["Comprension_Puntaje"]
    ]
    return df


class ComprehensionClassifier(Protocol):
    """Interfaz que deberá cumplir un clasificador futuro (por ejemplo, uno
    de scikit-learn): fit(X, y) y predict(X)."""

    def fit(self, X, y): ...

    def predict(self, X): ...


def training_table(features: pd.DataFrame, feature_columns: list[str]) -> tuple[pd.DataFrame, pd.Series]:
    """X (features) e y (Comprension_Alta) solo con las filas que tienen
    puntaje y datos suficientes: lo que recibiría ComprehensionClassifier.fit."""
    usable = features[
        features["Comprension_Alta"].notna() & ~features["Datos_Insuficientes"].astype(bool)
    ]
    return usable[feature_columns], usable["Comprension_Alta"].astype(bool)
