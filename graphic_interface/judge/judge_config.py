"""Configuración del juez (LLM-as-a-judge), en un solo lugar para poder
citarla tal cual en la tesis.

Sigue el mismo criterio que el resto del panel: constantes de módulo, y solo
lo que puede cambiar entre equipos (el modelo y la clave) se lee de
variables de entorno o del `.env` de la raíz del proyecto (ver
consent/consent_mailer.py, que hace lo mismo con el SMTP).
"""

import os
from typing import Optional

from dotenv import dotenv_values

from paths import JUDGE_RESULTS_DIR, PROJECT_ROOT

ENV_FILE = PROJECT_ROOT / ".env"

# Por dónde se llama al modelo juez (variable de entorno JUDGE_PROVIDER):
# - "api" (por defecto): SDK oficial de Anthropic con ANTHROPIC_API_KEY. Se
#   paga por uso y es el único que permite fijar la temperatura en 0.
# - "cli": el CLI `claude` con la suscripción de Claude (Pro/Max) con la que
#   ya se inició sesión, sin clave ni costo adicional. El CLI NO permite
#   fijar la temperatura: usa la del modelo por defecto, así que hay más
#   variación entre repeticiones, y las llamadas cuentan contra el límite de
#   uso de la suscripción. Cada llamada registra con qué proveedor se hizo y
#   las de uno no se mezclan con las del otro.
JUDGE_PROVIDER_ENV = "JUDGE_PROVIDER"
PROVIDER_API = "api"
PROVIDER_CLI = "cli"
CLAUDE_BIN = "claude"
# El CLI siempre lleva un system prompt propio (el de Claude Code); se
# reemplaza por este, mínimo, para que el juez reciba casi lo mismo que por
# la API (donde no hay system prompt).
JUDGE_CLI_SYSTEM_PROMPT = "Eres un evaluador. Responde únicamente con el JSON solicitado."

# La clave de la API NUNCA va en el código: se lee de la variable de entorno
# (o del `.env`, que no se sube al repo).
ANTHROPIC_API_KEY_ENV = "ANTHROPIC_API_KEY"

# Versión exacta del modelo juez, fija durante todo el estudio. Se puede
# pisar con la variable de entorno JUDGE_MODEL sin tocar código (mismo
# criterio que GEMINI_MODEL en ai/ai_backend.py), pero cada llamada guarda
# el modelo usado, así que una corrida con otro modelo no se mezcla con esta.
JUDGE_MODEL_ENV = "JUDGE_MODEL"
DEFAULT_JUDGE_MODEL = "claude-sonnet-5-5"

# Temperatura 0: la respuesta más probable, para reducir la variación entre
# repeticiones. No la elimina del todo (la API no garantiza determinismo ni
# acepta una semilla), y por eso cada prompt se evalúa varias veces.
JUDGE_TEMPERATURE = 0
JUDGE_MAX_TOKENS = 4000
JUDGE_REPETITIONS = 3

# Semilla del orden de evaluación (no de la API): mezcla los prompts para
# que los de un mismo nivel o generador no vayan seguidos, y siempre igual.
JUDGE_SEED = 20261013

# Versión de la plantilla del prompt del juez (assets/juez/rubrica.md). Hay
# que subirla a mano cada vez que cambie la plantilla, la rúbrica, las reglas
# o una ficha. Como respaldo, cada llamada guarda además un hash del texto
# realmente enviado (ver judge_prompt.context_hash).
JUDGE_TEMPLATE_VERSION = "1.1"  # 1.1: Game-01 sin el bono de puntos

# Respuesta que no cumple el formato: se repite la llamada una vez.
JUDGE_INVALID_RETRIES = 1

# Errores de red, límite de uso (429) o servidor (5xx): reintentos con espera
# creciente (2 s, 4 s, 8 s... hasta el máximo), o lo que indique la cabecera
# `retry-after` de la API.
JUDGE_NETWORK_RETRIES = 5
JUDGE_RETRY_BASE_SECONDS = 2.0
JUDGE_RETRY_MAX_SECONDS = 60.0
JUDGE_TIMEOUT_SECONDS = 120.0

# Si fallan tantas llamadas seguidas (por ejemplo, sin internet), la corrida
# se detiene en vez de registrar cientos de errores; lo ya guardado queda y
# se reanuda después.
JUDGE_MAX_CONSECUTIVE_FAILURES = 5

# Llamadas en paralelo. A temperatura 0 cada llamada es independiente, así
# que no altera los puntajes; solo acorta la corrida.
JUDGE_MAX_WORKERS = 4

# Solo para --estimar (no usa la API): tokens aproximados por carácter de
# texto en español y tokens de salida típicos de una respuesta del juez.
JUDGE_CHARS_PER_TOKEN = 3.2
JUDGE_ESTIMATED_OUTPUT_TOKENS = 1000
# Precio en USD por millón de tokens del modelo juez. Se dejan vacíos a
# propósito: hay que completarlos con el precio vigente en la página de
# precios de Anthropic (o con las variables de entorno de abajo) para que
# --estimar muestre el costo además de los tokens.
JUDGE_PRICE_INPUT_ENV = "JUDGE_PRICE_INPUT_PER_MTOK"
JUDGE_PRICE_OUTPUT_ENV = "JUDGE_PRICE_OUTPUT_PER_MTOK"

# Una carpeta de resultados por origen de los prompts.
SOURCE_SYNTHETIC = "dataset_sintetico"
SOURCE_SESSIONS = "sesiones"  # reservado: prompts reales de Etapa_3/intento_<N>
CALLS_FILE_NAME = "llamadas.jsonl"
RESULTS_FILE_NAME = "resultados.csv"
ANALYSIS_DIR_NAME = "analisis"


def results_dir(source: str = SOURCE_SYNTHETIC):
    return JUDGE_RESULTS_DIR / source


def _read_setting(key: str) -> str:
    """Una variable de entorno ya exportada tiene prioridad sobre el `.env`
    (que se lee sin volcarlo a os.environ)."""
    file_values = dotenv_values(ENV_FILE) if ENV_FILE.exists() else {}
    return (os.environ.get(key) or file_values.get(key) or "").strip()


def judge_provider() -> str:
    """ "api" salvo que JUDGE_PROVIDER valga exactamente "cli"."""
    return PROVIDER_CLI if _read_setting(JUDGE_PROVIDER_ENV).lower() == PROVIDER_CLI else PROVIDER_API


def judge_temperature() -> Optional[float]:
    """La temperatura realmente aplicada: None con el CLI, que no deja fijarla."""
    return JUDGE_TEMPERATURE if judge_provider() == PROVIDER_API else None


def judge_model() -> str:
    return _read_setting(JUDGE_MODEL_ENV) or DEFAULT_JUDGE_MODEL


def load_api_key() -> str:
    """Cadena vacía si no está configurada. Nunca se imprime ni se guarda."""
    return _read_setting(ANTHROPIC_API_KEY_ENV)


def _read_price(key: str) -> Optional[float]:
    try:
        return float(_read_setting(key))
    except ValueError:
        return None


def token_prices() -> tuple[Optional[float], Optional[float]]:
    """(entrada, salida) en USD por millón de tokens, o None si falta."""
    return _read_price(JUDGE_PRICE_INPUT_ENV), _read_price(JUDGE_PRICE_OUTPUT_ENV)
