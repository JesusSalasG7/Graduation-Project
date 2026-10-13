"""Análisis de la validación del juez (LLM-as-a-judge) sobre el dataset
sintético: lee data/juez/dataset_sintetico/resultados.csv (generado por
graphic_interface/scripts/evaluate_prompts.py o por el botón "Evaluar
prompts") y guarda las tablas y un resumen legible en la subcarpeta
analisis/.

Qué calcula:
1. Acuerdo entre el nivel pretendido de cada prompt y la mediana del nivel
   global que le dio el juez: matriz de confusión y kappa de Cohen con
   ponderación cuadrática, en total y por generador.
2. Kruskal-Wallis del nivel global entre generadores, para cada nivel
   pretendido: ¿el juez puntúa distinto según quién generó el prompt?
3. Correlación de Spearman entre el número de palabras y el nivel global
   dentro de cada nivel pretendido: sesgo de longitud.
4. Consistencia: porcentaje de prompts con las repeticiones idénticas y
   distribución de las diferencias entre repeticiones.

Este archivo no llama a la API: se puede correr todas las veces que haga falta.

Uso:
    .venv/bin/python data/analyze_judge.py [--resultados RUTA] [--salida CARPETA]
"""

import argparse
import warnings
from pathlib import Path

import pandas as pd
from scipy import stats
from sklearn.metrics import cohen_kappa_score, confusion_matrix

DATA_DIR = Path(__file__).resolve().parent
DEFAULT_RESULTS = DATA_DIR / "juez" / "dataset_sintetico" / "resultados.csv"
ANALYSIS_DIR_NAME = "analisis"

LEVELS = [1, 2, 3, 4]
INTENDED = "nivel_pretendido"
JUDGED = "nivel_global_mediana"
SCORE_KEYS = [
    "especificacion", "comportamiento", "restricciones", "casos_borde", "contexto_verificacion", "nivel_global",
]
ALL_GENERATORS = "Total"


def load_results(path: Path) -> tuple[pd.DataFrame, dict]:
    """Devuelve las filas utilizables y un conteo de las descartadas. Solo
    entran al análisis los prompts con una mediana entera del nivel global:
    con 2 repeticiones válidas la mediana puede dar x.5, que no es un nivel."""
    df = pd.read_csv(path)
    total = len(df)
    evaluated = df[df["repeticiones_validas"] > 0].copy()
    usable = evaluated[evaluated[JUDGED] % 1 == 0].copy()
    usable[JUDGED] = usable[JUDGED].astype(int)
    usable[INTENDED] = usable[INTENDED].astype(int)
    counts = {
        "filas": total,
        "sin_evaluacion_valida": total - len(evaluated),
        "mediana_no_entera": len(evaluated) - len(usable),
        "analizadas": len(usable),
    }
    return usable, counts


def confusion_table(df: pd.DataFrame) -> pd.DataFrame:
    """Filas = nivel pretendido, columnas = nivel global del juez."""
    matrix = confusion_matrix(df[INTENDED], df[JUDGED], labels=LEVELS)
    table = pd.DataFrame(matrix, index=LEVELS, columns=[f"juez_{level}" for level in LEVELS])
    table.index.name = INTENDED
    return table


def agreement_row(scope: str, df: pd.DataFrame) -> dict:
    """Kappa ponderado cuadrático: penaliza más un desacuerdo de 2 o 3
    niveles que uno de 1, que es lo adecuado para una escala ordinal."""
    kappa = float("nan")
    if len(df) and (df[INTENDED].nunique() > 1 or df[JUDGED].nunique() > 1):
        kappa = cohen_kappa_score(df[INTENDED], df[JUDGED], weights="quadratic", labels=LEVELS)
    difference = (df[JUDGED] - df[INTENDED]).abs()
    return {
        "ambito": scope,
        "n": len(df),
        "kappa_cuadratico": kappa,
        "acuerdo_exacto_pct": 100 * (difference == 0).mean() if len(df) else float("nan"),
        "acuerdo_adyacente_pct": 100 * (difference <= 1).mean() if len(df) else float("nan"),
        # Positivo = el juez puntúa más alto que el nivel pretendido.
        "diferencia_media": (df[JUDGED] - df[INTENDED]).mean() if len(df) else float("nan"),
    }


def kruskal_table(df: pd.DataFrame) -> pd.DataFrame:
    """Una fila por nivel pretendido. Si todos los puntajes de ese nivel son
    iguales la prueba no se puede calcular (no hay variación que comparar):
    queda vacía y se anota el motivo."""
    generators = sorted(df["generador"].unique())
    rows = []
    for level in LEVELS:
        subset = df[df[INTENDED] == level]
        groups = [subset[subset["generador"] == name][JUDGED] for name in generators]
        row = {INTENDED: level, "n": len(subset), "H": float("nan"), "p": float("nan"), "nota": ""}
        for name, group in zip(generators, groups):
            row[f"media_{name}"] = group.mean() if len(group) else float("nan")
        non_empty = [group for group in groups if len(group)]
        if len(non_empty) < 2:
            row["nota"] = "menos de dos generadores con datos"
        elif subset[JUDGED].nunique() < 2:
            row["nota"] = "todos los puntajes son iguales"
        else:
            row["H"], row["p"] = stats.kruskal(*non_empty)
        rows.append(row)
    return pd.DataFrame(rows)


def spearman_table(df: pd.DataFrame) -> pd.DataFrame:
    """Sesgo de longitud: dentro de un mismo nivel pretendido, la calidad
    buscada es la misma, así que una correlación positiva entre palabras y
    puntaje indica que el juez premia la longitud."""
    rows = []
    for level in LEVELS:
        subset = df[df[INTENDED] == level]
        row = {INTENDED: level, "n": len(subset), "rho": float("nan"), "p": float("nan"), "nota": ""}
        if len(subset) < 3:
            row["nota"] = "menos de 3 prompts"
        elif subset[JUDGED].nunique() < 2 or subset["palabras"].nunique() < 2:
            row["nota"] = "sin variación en una de las variables"
        else:
            row["rho"], row["p"] = stats.spearmanr(subset["palabras"], subset[JUDGED])
        rows.append(row)
    return pd.DataFrame(rows)


def consistency_tables(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(resumen, distribución). La diferencia de un puntaje es su máximo
    menos su mínimo entre las repeticiones de un mismo prompt."""
    complete = df[df["repeticiones_validas"] == df["repeticiones_validas"].max()]
    summary = pd.DataFrame([{
        "prompts": len(df),
        "con_todas_las_repeticiones": len(complete),
        "identicas_los_6_puntajes_pct": 100 * complete["repeticiones_identicas"].mean() if len(complete) else float("nan"),
        "identicas_nivel_global_pct": 100 * (complete["nivel_global_dif_max"] == 0).mean() if len(complete) else float("nan"),
    }])
    distribution = pd.DataFrame({
        key: complete[f"{key}_dif_max"].value_counts().reindex(range(4), fill_value=0)
        for key in SCORE_KEYS
    })
    distribution.index.name = "diferencia_maxima"
    return summary, distribution


def _markdown_table(table: pd.DataFrame, index: bool = False) -> str:
    """Tabla en Markdown sin depender del paquete `tabulate`."""
    if index:
        table = table.reset_index()

    def cell(value) -> str:
        if isinstance(value, float):
            if pd.isna(value):
                return "—"
            return "<0.001" if 0 < value < 0.001 else f"{value:.3f}"
        return str(value)

    lines = ["| " + " | ".join(str(column) for column in table.columns) + " |"]
    lines.append("| " + " | ".join("---" for _ in table.columns) + " |")
    for row in table.itertuples(index=False):
        lines.append("| " + " | ".join(cell(value) for value in row) + " |")
    return "\n".join(lines)


def analyze(results_file: Path = DEFAULT_RESULTS, output_dir: Path = None) -> Path:
    """Corre todo el análisis y devuelve la ruta del resumen."""
    output_dir = Path(output_dir) if output_dir else results_file.parent / ANALYSIS_DIR_NAME
    output_dir.mkdir(parents=True, exist_ok=True)
    df, counts = load_results(results_file)
    if df.empty:
        raise SystemExit(f"{results_file} no tiene prompts con una evaluación válida todavía.")

    generators = sorted(df["generador"].unique())
    scopes = [(ALL_GENERATORS, df)] + [(name, df[df["generador"] == name]) for name in generators]

    agreement = pd.DataFrame([agreement_row(scope, subset) for scope, subset in scopes])
    agreement.to_csv(output_dir / "kappa.csv", index=False)
    confusions = {}
    for scope, subset in scopes:
        confusions[scope] = confusion_table(subset)
        confusions[scope].to_csv(output_dir / f"matriz_confusion_{scope.lower()}.csv")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # avisos de scipy por empates; ya se anotan en "nota"
        kruskal = kruskal_table(df)
        spearman = spearman_table(df)
    kruskal.to_csv(output_dir / "kruskal_wallis.csv", index=False)
    spearman.to_csv(output_dir / "spearman_longitud.csv", index=False)

    consistency, distribution = consistency_tables(df)
    consistency.to_csv(output_dir / "consistencia.csv", index=False)
    distribution.to_csv(output_dir / "consistencia_diferencias.csv")

    model = ", ".join(sorted(df["modelo"].astype(str).unique()))
    version = ", ".join(sorted(df["version_plantilla"].astype(str).unique()))
    parts = [
        "# Validación del juez sobre el dataset sintético",
        f"Archivo analizado: `{results_file.name}` · modelo: {model} · plantilla v{version}",
        f"Prompts en el archivo: {counts['filas']} · analizados: {counts['analizadas']} · "
        f"sin evaluación válida: {counts['sin_evaluacion_valida']} · "
        f"con mediana no entera (excluidos): {counts['mediana_no_entera']}",
        "## 1. Acuerdo con el nivel pretendido",
        "Kappa de Cohen con ponderación cuadrática entre `nivel_pretendido` y la mediana de `nivel_global`. "
        "`diferencia_media` positiva significa que el juez puntúa más alto que el nivel pretendido.",
        _markdown_table(agreement),
    ]
    for scope, table in confusions.items():
        parts += [f"### Matriz de confusión · {scope}", "Filas: nivel pretendido. Columnas: nivel del juez.",
                  _markdown_table(table, index=True)]
    parts += [
        "## 2. Diferencias entre generadores (Kruskal-Wallis)",
        "Para cada nivel pretendido, compara el nivel global entre generadores. Un p menor que 0,05 indica "
        "que el juez puntúa distinto según el generador dentro de ese nivel.",
        _markdown_table(kruskal),
        "## 3. Sesgo de longitud (Spearman)",
        "Correlación entre el número de palabras y el nivel global dentro de cada nivel pretendido. "
        "Un rho positivo y significativo indica que el juez premia los prompts más largos.",
        _markdown_table(spearman),
        "## 4. Consistencia entre repeticiones",
        _markdown_table(consistency),
        "Cantidad de prompts según la diferencia máxima (máximo − mínimo) de cada puntaje entre repeticiones:",
        _markdown_table(distribution, index=True),
    ]
    summary_path = output_dir / "resumen.md"
    summary_path.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    return summary_path


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--resultados", type=Path, default=DEFAULT_RESULTS,
                        help=f"CSV de resultados del juez (default: {DEFAULT_RESULTS})")
    parser.add_argument("--salida", type=Path, default=None,
                        help="Carpeta de salida (default: analisis/ junto al CSV)")
    args = parser.parse_args()
    if not args.resultados.exists():
        raise SystemExit(f"No existe {args.resultados}. Primero corre graphic_interface/scripts/evaluate_prompts.py")
    summary_path = analyze(args.resultados, args.salida)
    print(summary_path.read_text(encoding="utf-8"))
    print(f"Tablas y resumen guardados en {summary_path.parent}")


if __name__ == "__main__":
    main()
