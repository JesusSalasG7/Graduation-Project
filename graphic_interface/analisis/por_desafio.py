"""Resultados separados por desafío (selector "Desafío" de la pestaña
Análisis y resultados_por_desafio.csv).

No cambia el procesamiento: parte de las mismas muestras que deja el
pipeline (ya filtradas por calidad y con el z calculado con TODAS las
muestras válidas del participante) y solo cambia la agrupación: mediana de
los z por participante × desafío × etapa, en vez de juntar los desafíos.
Así un z de un desafío se lee igual que en la tabla general (0 = nivel
habitual de la persona en toda la sesión).

El puntaje es el % de aciertos del cuestionario de ESE desafío. Las tablas
tienen las mismas columnas que resultados_por_etapa (más desafio y juego),
para que los gráficos funcionen igual sobre un solo desafío.
"""

import numpy as np
import pandas as pd

from analisis.config import ConfigAnalisis
from analisis.pipeline import (
    COL_CORRECTAS, COL_DESAFIO, COL_ETAPA, COL_PARTICIPANTE, COL_TOTAL_PREGUNTAS, COLUMNAS_RESULTADO,
    COLUMNAS_Z, _duracion_por_etapa, normalizar_etapa,
)

COL_JUEGO = "Juego"
COLUMNAS_POR_DESAFIO = ["desafio", "juego", *COLUMNAS_RESULTADO, "n_muestras"]
CLAVES = ["participante", "desafio", "etapa"]


def _dataset_por_desafio(dataset: pd.DataFrame) -> pd.DataFrame:
    ds = pd.DataFrame({
        "participante": dataset[COL_PARTICIPANTE],
        "desafio": dataset[COL_DESAFIO] if COL_DESAFIO in dataset else 1,
        "etapa": dataset[COL_ETAPA].map(normalizar_etapa),
        "juego": dataset[COL_JUEGO] if COL_JUEGO in dataset else "",
        "_dur": _duracion_por_etapa(dataset),
        "correctas": pd.to_numeric(dataset.get(COL_CORRECTAS), errors="coerce"),
        "total": pd.to_numeric(dataset.get(COL_TOTAL_PREGUNTAS), errors="coerce"),
    })
    return ds


def resultados_por_desafio(
    muestras: pd.DataFrame, dataset: pd.DataFrame, cfg: ConfigAnalisis = ConfigAnalisis(),
) -> tuple[pd.DataFrame, list[str]]:
    """Una fila por participante × desafío × etapa con la MEDIANA de los z
    (mismo criterio que agregar_por_etapa). Una celda con menos de
    MIN_MUESTRAS_VALIDAS muestras válidas queda con los z vacíos (mismo
    umbral que el control de calidad por etapa) y se avisa.

    pct_muestras_validas queda vacío: el reporte de calidad es por etapa
    (todos los desafíos juntos); n_muestras dice cuántas muestras válidas
    entraron en cada celda."""
    avisos: list[str] = []
    if muestras.empty:
        return pd.DataFrame(columns=COLUMNAS_POR_DESAFIO), avisos

    g = muestras.groupby(CLAVES, sort=True)
    agregado = g[COLUMNAS_Z].median()
    agregado["attention_prom"] = g["attention"].apply(lambda s: s[s > 0].mean())
    agregado["meditation_prom"] = g["meditation"].apply(lambda s: s[s > 0].mean())
    agregado["n_muestras"] = g.size()
    agregado = agregado.reset_index()

    pocas = agregado["n_muestras"] < cfg.min_muestras_validas
    for r in agregado[pocas].itertuples():
        avisos.append(f"P{r.participante} · desafío {r.desafio} · {r.etapa}: solo {r.n_muestras} muestras "
                      f"válidas (< {cfg.min_muestras_validas}); sin z en la vista por desafío.")
    agregado.loc[pocas, COLUMNAS_Z] = np.nan

    ds = _dataset_por_desafio(dataset)
    duracion = ds.groupby(CLAVES)["_dur"].sum(min_count=1).rename("duracion_s").reset_index()
    agregado = agregado.merge(duracion, on=CLAVES, how="left")
    agregado["duracion_s"] = agregado["duracion_s"].fillna(agregado["n_muestras"].astype(float))

    q = ds[ds["etapa"].isin(cfg.etapas_con_cuestionario)].dropna(subset=["correctas", "total"])
    q = q[q["total"] > 0].groupby(CLAVES)[["correctas", "total"]].sum()
    puntaje = (100.0 * q["correctas"] / q["total"]).rename("puntaje").reset_index()
    agregado = agregado.merge(puntaje, on=CLAVES, how="left")
    agregado.loc[agregado["etapa"] == cfg.etapa_sin_cuestionario, "puntaje"] = np.nan

    juegos = ds.dropna(subset=["juego"]).drop_duplicates("desafio").set_index("desafio")["juego"]
    agregado["juego"] = agregado["desafio"].map(juegos).fillna("")
    agregado["pct_muestras_validas"] = np.nan

    orden = {e: i for i, e in enumerate(cfg.etapas_analisis)}
    agregado = agregado.sort_values(
        CLAVES, key=lambda s: s.map(orden) if s.name == "etapa" else s,
    ).reset_index(drop=True)
    return agregado[COLUMNAS_POR_DESAFIO], avisos


def desafios_disponibles(por_desafio: pd.DataFrame) -> list[tuple[int, str]]:
    """[(desafío, "Desafío N · Juego")] en orden."""
    if por_desafio.empty:
        return []
    pares = por_desafio.drop_duplicates("desafio").sort_values("desafio")
    return [
        (int(r.desafio), f"Desafío {int(r.desafio)}" + (f" · {r.juego}" if r.juego else ""))
        for r in pares.itertuples()
    ]


def vista_desafio(por_desafio: pd.DataFrame, desafio: int) -> pd.DataFrame:
    """Filas de un desafío con las columnas de resultados_por_etapa, para
    pasarlas tal cual a los gráficos."""
    return por_desafio[por_desafio["desafio"] == desafio][COLUMNAS_RESULTADO].reset_index(drop=True)
