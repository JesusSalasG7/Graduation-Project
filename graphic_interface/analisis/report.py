"""Resúmenes de la tabla de features para mostrar en la interfaz (gráfico
por etapa e indicadores de calidad). Funciones puras, igual que
eeg_features.py."""

from typing import Optional

import pandas as pd

STAGE_NAMES = {
    2: "El problema",
    3: "Tu prompt",
    4: "Resultado",
    5: "Razonamiento",
}


def filter_participant(features: pd.DataFrame, participant: Optional[int]) -> pd.DataFrame:
    """participant=None -> todos."""
    if participant is None or features.empty:
        return features
    return features[features["Participante_ID"] == participant]


def stage_summary(features: pd.DataFrame) -> pd.DataFrame:
    """Una fila por etapa, solo con las filas con datos suficientes: cuántas
    hay, media de EEG1/EEG2 y media de su cambio % contra la línea base."""
    columns = ["Etapa", "Filas", "EEG1_Media", "EEG2_Media", "EEG1_Media_Cambio_Pct", "EEG2_Media_Cambio_Pct"]
    if features.empty:
        return pd.DataFrame(columns=columns)
    valid = features[~features["Datos_Insuficientes"].astype(bool)]
    if valid.empty:
        return pd.DataFrame(columns=columns)
    grouped = valid.groupby("Etapa")
    summary = grouped[columns[2:]].mean()
    summary.insert(0, "Filas", grouped.size())
    return summary.reset_index()[columns]


def quality_summary(features: pd.DataFrame) -> dict:
    """Indicadores de calidad: % descartado medio por etapa, filas con datos
    insuficientes, filas con δ atípica y si hay línea base."""
    if features.empty:
        return {"pct_descartado_por_etapa": {}, "insuficientes": [], "delta_alta": [], "con_linea_base": 0, "filas": 0}

    def describe(row) -> str:
        return f"P{row['Participante_ID']} · Desafío {row['Desafio']} · Etapa {row['Etapa']} · Intento {row['Intento']}"

    return {
        "pct_descartado_por_etapa": features.groupby("Etapa")["Pct_Descartado"].mean().round(1).to_dict(),
        "insuficientes": [describe(r) for _, r in features[features["Datos_Insuficientes"].astype(bool)].iterrows()],
        "delta_alta": [describe(r) for _, r in features[features["Delta_Atipica"].astype(bool)].iterrows()],
        "con_linea_base": int(features["Linea_Base_Disponible"].astype(bool).sum()),
        "filas": len(features),
    }
