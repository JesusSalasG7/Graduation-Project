"""Pruebas estadísticas sobre la tabla resultados_por_etapa.

Todas devuelven filas con el mismo formato (COLUMNAS_ESTADISTICA) para
juntarlas en resultados_estadisticos.csv. Siempre se informa el tamaño de
efecto junto al valor p (alfa = 0,05).

Con muestras pequeñas (n = 10 participantes en los datos actuales) los
resultados son exploratorios: las pruebas no paramétricas tienen poca
potencia y el modelo mixto no se ajusta por debajo de 15 participantes.
"""

import itertools
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats

from analisis.config import ConfigAnalisis

COLUMNAS_ESTADISTICA = [
    "analisis", "indicador", "etapa", "n", "estadistico", "valor",
    "p", "p_holm", "efecto", "valor_efecto", "significativo", "nota",
]
NOTA_MUESTRA_PEQUENA = "muestra pequeña: resultados exploratorios"


def _fila(**kw) -> dict:
    fila = {c: np.nan for c in COLUMNAS_ESTADISTICA}
    fila.update({"nota": ""})
    fila.update(kw)
    return fila


def _r_desde_p(p: float, n: int, signo: float = 1.0) -> float:
    """Tamaño de efecto r = Z / √N, con Z recuperado del valor p bilateral
    (Rosenthal, 1991). Sirve tanto para Wilcoxon (N = pares) como para
    Mann-Whitney (N = n1 + n2), sin importar si scipy usó la distribución
    exacta o la aproximación normal."""
    if not np.isfinite(p) or n <= 0:
        return float("nan")
    z = stats.norm.isf(max(p, 1e-300) / 2)
    return float(np.sign(signo) * z / np.sqrt(n)) if signo != 0 else 0.0


def holm(pvalores: list[float]) -> list[float]:
    """Corrección de Holm-Bonferroni (controla el error de familia, menos
    conservadora que Bonferroni). Los NaN se mantienen."""
    p = np.asarray(pvalores, dtype=float)
    validos = np.where(np.isfinite(p))[0]
    ajustados = np.full(p.shape, np.nan)
    m = len(validos)
    orden = validos[np.argsort(p[validos])]
    acumulado = 0.0
    for rango, idx in enumerate(orden):
        acumulado = max(acumulado, min(1.0, (m - rango) * p[idx]))
        ajustados[idx] = acumulado
    return ajustados.tolist()


# ============================================================
# Diferencias entre etapas
# ============================================================

def friedman_etapas(
    resultados: pd.DataFrame, indicador: str, cfg: ConfigAnalisis = ConfigAnalisis(),
) -> list[dict]:
    """Friedman (medidas repetidas no paramétricas) entre las etapas del
    análisis para <indicador>_z, con W de Kendall = χ² / (n·(k − 1)).
    Solo entran los participantes con dato en TODAS las etapas. Si es
    significativa, Wilcoxon por pares con corrección de Holm y r."""
    etapas = list(cfg.etapas_analisis)
    col = f"{indicador}_z"
    ancho = resultados.pivot_table(index="participante", columns="etapa", values=col, aggfunc="first")
    ancho = ancho.reindex(columns=etapas).dropna()
    n, k = len(ancho), len(etapas)
    nombre_etapas = f"{etapas[0]}–{etapas[-1]}"
    if n < 3:
        return [_fila(analisis="Friedman", indicador=col, etapa=nombre_etapas, n=n,
                      nota=f"menos de 3 participantes con datos en las {k} etapas")]

    chi2, p = stats.friedmanchisquare(*[ancho[e].to_numpy() for e in etapas])
    w = chi2 / (n * (k - 1))
    sig = bool(p < cfg.alfa)
    filas = [_fila(
        analisis="Friedman", indicador=col, etapa=nombre_etapas, n=n, estadistico="χ²",
        valor=chi2, p=p, efecto="W de Kendall", valor_efecto=w, significativo=sig,
        nota=f"{n} participantes con datos válidos en las {k} etapas",
    )]
    if not sig:
        return filas

    pares = list(itertools.combinations(etapas, 2))
    crudas = []
    for a, b in pares:
        dif = ancho[a] - ancho[b]
        if np.allclose(dif, 0):
            crudas.append((a, b, np.nan, np.nan, 0.0))
            continue
        res = stats.wilcoxon(ancho[a], ancho[b])
        crudas.append((a, b, res.statistic, res.pvalue, float(np.median(dif))))
    ajustadas = holm([c[3] for c in crudas])
    for (a, b, est, p_par, mediana_dif), p_adj in zip(crudas, ajustadas):
        filas.append(_fila(
            analisis="Wilcoxon por pares", indicador=col, etapa=f"{a} vs {b}", n=n,
            estadistico="W", valor=est, p=p_par, p_holm=p_adj, efecto="r",
            valor_efecto=_r_desde_p(p_par, n, mediana_dif),
            significativo=bool(np.isfinite(p_adj) and p_adj < cfg.alfa),
            nota="r > 0: la primera etapa es mayor",
        ))
    return filas


# ============================================================
# Relación EEG–comprensión
# ============================================================

def _spearman(x: pd.Series, y: pd.Series) -> tuple[float, float, int]:
    ok = x.notna() & y.notna()
    n = int(ok.sum())
    if n < 3 or x[ok].nunique() < 2 or y[ok].nunique() < 2:
        return float("nan"), float("nan"), n
    rho, p = stats.spearmanr(x[ok], y[ok])
    return float(rho), float(p), n


def spearman_comprension(resultados: pd.DataFrame, cfg: ConfigAnalisis = ConfigAnalisis()) -> list[dict]:
    """ρ de Spearman entre EEG1_z / EEG2_z y el % de aciertos en cada etapa
    con cuestionario y con las tres etapas agrupadas. Spearman porque el
    puntaje es ordinal y acotado (0–100 %) y la relación no tiene por qué
    ser lineal. Ojo: el agrupado repite participantes (no independiente)."""
    filas = []
    con_q = resultados[resultados["etapa"].isin(cfg.etapas_con_cuestionario)]
    grupos = [(e, con_q[con_q["etapa"] == e]) for e in cfg.etapas_con_cuestionario]
    grupos.append(("Agrupadas (" + ", ".join(cfg.etapas_con_cuestionario) + ")", con_q))
    for indicador in ("EEG1_z", "EEG2_z"):
        for etapa, df in grupos:
            rho, p, n = _spearman(df[indicador], df["puntaje"])
            nota = "" if np.isfinite(rho) else "datos insuficientes o sin variación"
            if etapa.startswith("Agrupadas") and np.isfinite(rho):
                nota = "observaciones repetidas por participante (no independientes)"
            filas.append(_fila(
                analisis="Spearman EEG–comprensión", indicador=indicador, etapa=etapa, n=n,
                estadistico="ρ", valor=rho, p=p, efecto="ρ", valor_efecto=rho,
                significativo=bool(np.isfinite(p) and p < cfg.alfa), nota=nota,
            ))
    return filas


def grupos_comprension(resultados: pd.DataFrame, cfg: ConfigAnalisis = ConfigAnalisis()) -> pd.DataFrame:
    """Divide a los participantes de cada etapa con cuestionario por la
    mediana del puntaje de ESA etapa: ≥ mediana = "Comprensión alta",
    < mediana = "Comprensión baja"."""
    df = resultados[resultados["etapa"].isin(cfg.etapas_con_cuestionario)].dropna(subset=["puntaje"]).copy()
    mediana = df.groupby("etapa")["puntaje"].transform("median")
    df["grupo"] = np.where(df["puntaje"] >= mediana, "Comprensión alta", "Comprensión baja")
    return df


def mann_whitney_comprension(resultados: pd.DataFrame, cfg: ConfigAnalisis = ConfigAnalisis()) -> list[dict]:
    """Mann-Whitney U (alta vs baja comprensión) para EEG1_z y EEG2_z en
    cada etapa con cuestionario, con r = Z/√N (r > 0: el grupo alto tiene
    valores mayores)."""
    filas = []
    df = grupos_comprension(resultados, cfg)
    for indicador in ("EEG1_z", "EEG2_z"):
        for etapa in cfg.etapas_con_cuestionario:
            sub = df[df["etapa"] == etapa].dropna(subset=[indicador])
            alta = sub.loc[sub["grupo"] == "Comprensión alta", indicador]
            baja = sub.loc[sub["grupo"] == "Comprensión baja", indicador]
            n = len(alta) + len(baja)
            if len(alta) == 0 or len(baja) == 0:
                filas.append(_fila(
                    analisis="Mann-Whitney alta vs baja", indicador=indicador, etapa=etapa, n=n,
                    nota="un grupo vacío (muchos puntajes iguales a la mediana)",
                ))
                continue
            res = stats.mannwhitneyu(alta, baja, alternative="two-sided")
            filas.append(_fila(
                analisis="Mann-Whitney alta vs baja", indicador=indicador, etapa=etapa, n=n,
                estadistico="U", valor=res.statistic, p=res.pvalue, efecto="r",
                valor_efecto=_r_desde_p(res.pvalue, n, float(np.median(alta) - np.median(baja))),
                significativo=bool(res.pvalue < cfg.alfa),
                nota=f"alta n={len(alta)}, baja n={len(baja)}; r > 0: alta mayor",
            ))
    return filas


def modelo_mixto(resultados: pd.DataFrame, cfg: ConfigAnalisis = ConfigAnalisis()) -> list[dict]:
    """Modelo lineal mixto puntaje ~ EEG1_z + EEG2_z + etapa + (1 | participante)
    con las etapas con cuestionario. El intercepto aleatorio absorbe que
    cada participante aporta varias etapas. Solo se ajusta con
    MIN_PARTICIPANTES_MODELO_MIXTO o más participantes."""
    df = resultados[resultados["etapa"].isin(cfg.etapas_con_cuestionario)].dropna(
        subset=["puntaje", "EEG1_z", "EEG2_z"]
    )
    n_part = df["participante"].nunique()
    base = dict(analisis="Modelo lineal mixto", indicador="puntaje ~ EEG1_z + EEG2_z + etapa + (1|participante)")
    if n_part < cfg.min_participantes_modelo_mixto:
        return [_fila(**base, etapa="—", n=n_part,
                      nota=f"{NOTA_MUESTRA_PEQUENA} (n = {n_part} < {cfg.min_participantes_modelo_mixto}); no se ajustó")]
    try:
        import statsmodels.formula.api as smf
    except ImportError:
        return [_fila(**base, etapa="—", n=n_part, nota="statsmodels no está instalado; no se ajustó")]
    datos = df.rename(columns={"etapa": "etapa_cat"})
    ajuste = smf.mixedlm("puntaje ~ EEG1_z + EEG2_z + C(etapa_cat)", datos, groups=datos["participante"]).fit()
    filas = []
    for termino in ajuste.fe_params.index:
        filas.append(_fila(
            **base, etapa=termino, n=len(datos), estadistico="β", valor=ajuste.fe_params[termino],
            p=ajuste.pvalues[termino], efecto="β (puntos de % por 1 DE)", valor_efecto=ajuste.fe_params[termino],
            significativo=bool(ajuste.pvalues[termino] < cfg.alfa), nota=f"{n_part} participantes",
        ))
    return filas


def tabla_estadistica(resultados: pd.DataFrame, cfg: ConfigAnalisis = ConfigAnalisis()) -> pd.DataFrame:
    """Todas las pruebas en una tabla (resultados_estadisticos.csv)."""
    filas: list[dict] = []
    for ind in ("EEG1", "EEG2"):
        filas += friedman_etapas(resultados, ind, cfg)
    filas += spearman_comprension(resultados, cfg)
    filas += mann_whitney_comprension(resultados, cfg)
    filas += modelo_mixto(resultados, cfg)
    tabla = pd.DataFrame(filas, columns=COLUMNAS_ESTADISTICA)
    n_part = resultados["participante"].nunique()
    if n_part < cfg.min_participantes_modelo_mixto:
        tabla["nota"] = [
            (n + "; " if n else "") + NOTA_MUESTRA_PEQUENA if NOTA_MUESTRA_PEQUENA not in n else n
            for n in tabla["nota"].fillna("")
        ]
    return tabla


def spearman_panel(df: pd.DataFrame, indicador: str) -> tuple[float, float, int]:
    """ρ, p y n para el título de un panel del gráfico de dispersión."""
    return _spearman(df[indicador], df["puntaje"])


def mediana_grupo(resultados: pd.DataFrame, indicador: str, etapas: list[str]) -> Optional[pd.Series]:
    """Mediana del grupo por etapa (para la línea gruesa del perfil)."""
    return resultados.groupby("etapa")[indicador].median().reindex(etapas)
