"""Parámetros del análisis EEG, en un solo lugar para poder citarlos tal
cual en la metodología de la tesis.

Los valores por defecto viven en las constantes de módulo; ConfigAnalisis
las agrupa para que las funciones del pipeline (y las pruebas) reciban los
parámetros explícitamente en vez de leer variables globales.
"""

from dataclasses import dataclass, field
from typing import Optional

from paths import PROJECT_DATA_DIR

# ------------------------------------------------------------------
# Entrada y salida
# ------------------------------------------------------------------
# Dataset consolidado que genera data/build_dataset.py.
RUTA_DATASET = PROJECT_DATA_DIR / "dataset_sesiones.csv"
# Carpeta de resultados (CSV y PNG). Son datos de participantes: va al
# .gitignore (regla "data/analisis/").
RUTA_SALIDA = PROJECT_DATA_DIR / "analisis"

# ------------------------------------------------------------------
# Etapas
# ------------------------------------------------------------------
ETAPAS_ANALISIS = ["Etapa 2", "Etapa 3", "Etapa 4", "Etapa 5"]
ETAPAS_CON_CUESTIONARIO = ["Etapa 2", "Etapa 4", "Etapa 5"]
ETAPA_SIN_CUESTIONARIO = "Etapa 3"
# Etapa de reposo usada como referencia para el z (por ejemplo "Etapa 1").
# None = la referencia son todas las muestras válidas de ETAPAS_ANALISIS.
ETAPA_LINEA_BASE: Optional[str] = None

# Descripción corta (ejes de los gráficos) y larga (tablas y textos).
DESCRIPCION_CORTA_ETAPA = {
    "Etapa 1": "Reposo",
    "Etapa 2": "Problema",
    "Etapa 3": "Prompt",
    "Etapa 4": "Solución",
    "Etapa 5": "Razonamiento",
}
DESCRIPCION_ETAPA = {
    "Etapa 2": "Lectura del problema",
    "Etapa 3": "Escribir el prompt",
    "Etapa 4": "Lectura de la solución",
    "Etapa 5": "Lectura del razonamiento",
}

# ------------------------------------------------------------------
# Control de calidad
# ------------------------------------------------------------------
# PoorSignal de NeuroSky: 0 = señal limpia, 200 = electrodo sin contacto.
# Se conservan las muestras con PoorSignal <= UMBRAL_POOR_SIGNAL. Con 0 solo
# entra la señal perfecta; para el criterio "< 50" usar 49 (es un entero).
UMBRAL_POOR_SIGNAL = 0
# Una etapa (participante × etapa) es de "baja calidad" si tiene menos de
# MIN_MUESTRAS_VALIDAS muestras válidas o menos de MIN_PCT_VALIDO % válido.
MIN_MUESTRAS_VALIDAS = 30
MIN_PCT_VALIDO = 50.0
# True = las etapas de baja calidad no entran en la normalización ni en
# los resultados (siguen apareciendo en el reporte de calidad).
EXCLUIR_BAJA_CALIDAD = True
# Control de artefactos con Delta (no es indicador de carga): % de muestras
# válidas cuyo log(Delta) supera la media del participante + 2 DE.
DELTA_Z_ARTEFACTO = 2.0

# ------------------------------------------------------------------
# Estadística
# ------------------------------------------------------------------
ALFA = 0.05
# Participantes mínimos para ajustar el modelo lineal mixto.
MIN_PARTICIPANTES_MODELO_MIXTO = 15

# ------------------------------------------------------------------
# Gráficos
# ------------------------------------------------------------------
COLOR_EEG1 = "#7F77DD"         # morado
COLOR_EEG2 = "#1D9E75"         # verde azulado
COLOR_COMPARACION = "#B4B2A9"  # gris del grupo de comparación (comprensión baja)
DPI_EXPORTACION = 300
# "barras" (por defecto) | "boxplot" | "lineas". Los dos últimos reactivan
# los gráficos anteriores (boxplots / líneas por participante).
TIPO_GRAFICO = "barras"
# Barras de error con el rango intercuartílico (Q1–Q3). Por defecto no:
# los puntos de cada participante ya muestran la variabilidad.
MOSTRAR_RIC = False
# Por debajo de este |z| (en EEG1 y EEG2 a la vez) el texto automático
# dice "cercano al nivel habitual".
UMBRAL_CERCANO_Z = 0.2


@dataclass(frozen=True)
class ConfigAnalisis:
    umbral_poor_signal: int = UMBRAL_POOR_SIGNAL
    min_muestras_validas: int = MIN_MUESTRAS_VALIDAS
    min_pct_valido: float = MIN_PCT_VALIDO
    excluir_baja_calidad: bool = EXCLUIR_BAJA_CALIDAD
    etapas_analisis: tuple = tuple(ETAPAS_ANALISIS)
    etapas_con_cuestionario: tuple = tuple(ETAPAS_CON_CUESTIONARIO)
    etapa_sin_cuestionario: str = ETAPA_SIN_CUESTIONARIO
    etapa_linea_base: Optional[str] = ETAPA_LINEA_BASE
    delta_z_artefacto: float = DELTA_Z_ARTEFACTO
    alfa: float = ALFA
    min_participantes_modelo_mixto: int = MIN_PARTICIPANTES_MODELO_MIXTO
    descripcion_corta: dict = field(default_factory=lambda: dict(DESCRIPCION_CORTA_ETAPA))
