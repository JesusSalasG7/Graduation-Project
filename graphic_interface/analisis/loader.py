"""Punto de entrada del análisis: lee el dataset, corre el pipeline, la
estadística y los gráficos, y exporta los resultados. Es lo único del
módulo (junto con cargar_dataset) que toca disco.

Uso desde la terminal (raíz del proyecto):
    .venv/bin/python graphic_interface/analisis/loader.py
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

if __name__ == "__main__":  # permite correrlo como script
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analisis.config import RUTA_DATASET, RUTA_SALIDA, ConfigAnalisis  # noqa: E402
from analisis.estadistica import tabla_estadistica  # noqa: E402
from analisis.pipeline import ResultadoPipeline, cargar_dataset, ejecutar_pipeline  # noqa: E402
from analisis.por_desafio import resultados_por_desafio  # noqa: E402

ARCHIVO_RESULTADOS = "resultados_por_etapa.csv"
ARCHIVO_ESTADISTICA = "resultados_estadisticos.csv"
ARCHIVO_CALIDAD = "reporte_calidad.csv"
ARCHIVO_POR_DESAFIO = "resultados_por_desafio.csv"


@dataclass
class ResultadoAnalisis:
    pipeline: ResultadoPipeline
    estadistica: pd.DataFrame
    figuras: dict  # clave -> matplotlib Figure (vacío si no hay datos)
    # participante × desafío × etapa (misma mediana de los mismos z, sin juntar desafíos)
    por_desafio: pd.DataFrame = field(default_factory=pd.DataFrame)
    avisos_por_desafio: list = field(default_factory=list)


def ejecutar_analisis(
    ruta: Path = RUTA_DATASET, cfg: ConfigAnalisis = ConfigAnalisis(), con_figuras: bool = True,
) -> ResultadoAnalisis:
    """dataset en disco -> tablas, estadística y figuras."""
    dataset = cargar_dataset(ruta)
    resultado = ejecutar_pipeline(dataset, cfg)
    por_desafio, avisos_desafio = resultados_por_desafio(resultado.muestras, dataset, cfg)
    estadistica = (
        tabla_estadistica(resultado.resultados, cfg) if not resultado.resultados.empty else pd.DataFrame()
    )
    figuras = {}
    if con_figuras and not resultado.resultados.empty:
        from analisis.graficos import generar_figuras  # matplotlib solo si hace falta
        figuras = generar_figuras(resultado.resultados, cfg)
    return ResultadoAnalisis(resultado, estadistica, figuras, por_desafio, avisos_desafio)


def exportar(analisis: ResultadoAnalisis, carpeta: Path = RUTA_SALIDA) -> Path:
    """Escribe resultados_por_etapa.csv, resultados_estadisticos.csv,
    reporte_calidad.csv, resultados_por_desafio.csv y los PNG (300 dpi)
    en `carpeta`."""
    carpeta.mkdir(parents=True, exist_ok=True)
    analisis.pipeline.resultados.to_csv(carpeta / ARCHIVO_RESULTADOS, index=False)
    analisis.estadistica.to_csv(carpeta / ARCHIVO_ESTADISTICA, index=False)
    analisis.pipeline.calidad.to_csv(carpeta / ARCHIVO_CALIDAD, index=False)
    analisis.por_desafio.to_csv(carpeta / ARCHIVO_POR_DESAFIO, index=False)
    if analisis.figuras:
        from analisis.graficos import guardar_figuras
        guardar_figuras(analisis.figuras, carpeta)
    return carpeta


if __name__ == "__main__":
    a = ejecutar_analisis()
    print(f"Etapas ignoradas: {a.pipeline.etapas_ignoradas or 'ninguna'}")
    for aviso in a.pipeline.avisos:
        print("Aviso:", aviso)
    print(f"Resultados exportados en {exportar(a)}")
