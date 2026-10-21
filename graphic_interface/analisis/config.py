"""Parámetros del análisis EEG, en un solo lugar para poder citarlos tal
cual en la tesis (mismo criterio que judge/judge_config.py).

Los valores por defecto viven en las constantes de módulo; AnalysisConfig
las agrupa para que las funciones de cálculo (y las pruebas) reciban los
parámetros explícitamente en vez de leer variables globales.
"""

from dataclasses import dataclass

from paths import PROJECT_DATA_DIR

# Dataset consolidado que genera data/build_dataset.py.
DATASET_FILE = PROJECT_DATA_DIR / "dataset_sesiones.csv"
# Tabla de features exportada. Son datos de participantes: va al
# .gitignore, igual que el dataset (ver regla "data/analisis/").
FEATURES_OUT_FILE = PROJECT_DATA_DIR / "analisis" / "eeg_features.csv"

# PoorSignal de NeuroSky: 0 = señal limpia, 200 = electrodo sin contacto.
# Se conservan las muestras con PoorSignal <= POOR_SIGNAL_THRESHOLD; las de
# 200 se descartan siempre, aunque el umbral se suba.
POOR_SIGNAL_THRESHOLD = 0
POOR_SIGNAL_NO_CONTACT = 200

# Una etapa con menos del 50 % de muestras válidas, o con menos de 10,
# queda marcada como "datos insuficientes" y no entra en la línea base,
# el z-score ni el Min-Max.
MIN_VALID_FRACTION = 0.5
MIN_VALID_SAMPLES = 10

# No hay una etapa de reposo grabada: se usa la Etapa 2 (leer el
# enunciado) del MISMO desafío como línea base. Elegido con el
# investigador; cambiar acá si más adelante se graba un reposo real.
BASELINE_STAGE = 2

# Alerta de artefactos: la media de log(δ) de la etapa está a más de este
# número de desviaciones estándar sobre la media del participante.
DELTA_ALERT_Z = 2.0

# Puntuación de comprensión (0–6) y umbral para binarizarla (alta/baja).
COMPREHENSION_MIN = 0.0
COMPREHENSION_MAX = 6.0
COMPREHENSION_THRESHOLD = 3.5


@dataclass(frozen=True)
class AnalysisConfig:
    poor_signal_threshold: int = POOR_SIGNAL_THRESHOLD
    min_valid_fraction: float = MIN_VALID_FRACTION
    min_valid_samples: int = MIN_VALID_SAMPLES
    baseline_stage: int = BASELINE_STAGE
    delta_alert_z: float = DELTA_ALERT_Z
    comprehension_threshold: float = COMPREHENSION_THRESHOLD
