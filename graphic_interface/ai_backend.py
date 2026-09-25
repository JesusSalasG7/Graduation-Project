"""Backend de IA configurable, usado por isolated_prompt.py (respuesta
aislada de la Etapa 2) y challenge_solver.py (generación de cuestionarios):
CLI `claude` (por defecto, sin API key propia -- ver README, sección
"Requisitos previos") o API de Gemini (Google AI Studio), si se configura
AI_PROVIDER=gemini + GEMINI_API_KEY.

Este modulo NO decide nada de negocio (system prompt,
contenido del JSON Schema de las preguntas): eso sigue viviendo en
isolated_prompt.py / challenge_solver.py, que llaman a run_isolated_prompt /
run_json_schema_prompt de aca sin saber que proveedor responde en realidad.
Asi, agregar un tercer proveedor a futuro no toca la logica de las
Etapas 2/3/4/5.
"""

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional

import requests

CLAUDE_BIN = "claude"

AI_PROVIDER_ENV = "AI_PROVIDER"
PROVIDER_CLAUDE = "claude"
PROVIDER_GEMINI = "gemini"

GEMINI_API_KEY_ENV = "GEMINI_API_KEY"
GEMINI_MODEL_ENV = "GEMINI_MODEL"
# gemini-2.5-flash quedo deprecado para cuentas nuevas (la API devuelve 404
# y recomienda este reemplazo) -- si Google vuelve a rotar el modelo
# recomendado, se puede pisar sin tocar codigo con la variable de entorno
# GEMINI_MODEL.
DEFAULT_GEMINI_MODEL = "gemini-3.6-flash"
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


@dataclass
class AIResult:
    ok: bool
    text: str = ""
    payload: Optional[dict] = None  # solo si se pidio json_schema -- ya parseado
    error: str = ""


def active_provider() -> str:
    """"claude" (default) o "gemini", segun la variable de entorno
    AI_PROVIDER -- cualquier otro valor (o ausente, o vacia) cae a "claude"
    para no romper instalaciones existentes que nunca configuraron nada."""
    value = os.environ.get(AI_PROVIDER_ENV, "").strip().lower()
    return PROVIDER_GEMINI if value == PROVIDER_GEMINI else PROVIDER_CLAUDE


def provider_available() -> bool:
    """True si el backend actualmente seleccionado (ver active_provider)
    esta listo para usarse: CLI 'claude' en el PATH, o GEMINI_API_KEY
    configurada. Se usa para avisar ANTES de arrancar la sesion guiada
    (ver app.py.enter_session_wizard), no al invocar la IA."""
    if active_provider() == PROVIDER_GEMINI:
        return bool(os.environ.get(GEMINI_API_KEY_ENV, "").strip())
    return shutil.which(CLAUDE_BIN) is not None


def provider_unavailable_reason() -> str:
    """Explica por que provider_available() dio False, para mostrarlo en
    el aviso previo a la sesion guiada."""
    if active_provider() == PROVIDER_GEMINI:
        return (
            f"AI_PROVIDER=gemini está activo pero no se encontró la variable de "
            f"entorno {GEMINI_API_KEY_ENV} con una API key válida de Google AI Studio."
        )
    return "No se encontró el CLI 'claude' instalado en este equipo."


def _gemini_model() -> str:
    return os.environ.get(GEMINI_MODEL_ENV, "").strip() or DEFAULT_GEMINI_MODEL


def _gemini_request(
    prompt: str, system_prompt: str, timeout: int, json_schema: Optional[dict],
) -> AIResult:
    api_key = os.environ.get(GEMINI_API_KEY_ENV, "").strip()
    if not api_key:
        return AIResult(ok=False, error=f"Falta la variable de entorno {GEMINI_API_KEY_ENV}.")

    generation_config = {}
    if json_schema is not None:
        generation_config["responseMimeType"] = "application/json"
        generation_config["responseSchema"] = json_schema

    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
    if system_prompt:
        body["systemInstruction"] = {"parts": [{"text": system_prompt}]}
    if generation_config:
        body["generationConfig"] = generation_config

    url = f"{GEMINI_API_BASE}/{_gemini_model()}:generateContent"
    try:
        response = requests.post(url, params={"key": api_key}, json=body, timeout=timeout)
    except requests.Timeout:
        return AIResult(ok=False, error=f"Gemini no respondió en {timeout}s.")
    except requests.RequestException as exc:
        return AIResult(ok=False, error=f"No se pudo contactar la API de Gemini: {exc}")

    if response.status_code != 200:
        return AIResult(
            ok=False,
            error=f"Gemini respondió con error {response.status_code}: {response.text.strip()[:500]}",
        )

    try:
        payload = response.json()
        candidates = payload.get("candidates") or []
        parts = candidates[0]["content"]["parts"]
        text = "".join(part.get("text", "") for part in parts).strip()
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        return AIResult(ok=False, error=f"Respuesta inesperada de Gemini: {exc}")

    if not text:
        return AIResult(ok=False, error="Gemini no devolvió ninguna respuesta.")

    if json_schema is not None:
        try:
            return AIResult(ok=True, text=text, payload=json.loads(text))
        except json.JSONDecodeError as exc:
            return AIResult(ok=False, error=f"Gemini no devolvió JSON válido: {exc}")

    return AIResult(ok=True, text=text)


def _claude_cli_request(
    prompt: str, system_prompt: str, model: str, timeout: int,
    json_schema: Optional[dict], cwd: Optional[str],
) -> AIResult:
    cmd = [CLAUDE_BIN, "-p", prompt, "--tools", "", "--model", model, "--output-format", "json"]
    if system_prompt:
        cmd += ["--system-prompt", system_prompt]
    if json_schema is not None:
        cmd += ["--json-schema", json.dumps(json_schema)]

    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return AIResult(ok=False, error="No se encontró el comando 'claude' en el PATH.")
    except subprocess.TimeoutExpired:
        return AIResult(ok=False, error=f"'claude' no respondió en {timeout}s.")

    if proc.returncode != 0:
        return AIResult(
            ok=False, error=f"'claude' terminó con error (código {proc.returncode}): {proc.stderr.strip()}",
        )

    try:
        payload = json.loads(proc.stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        return AIResult(ok=False, error=f"Respuesta inesperada de 'claude' (no es JSON): {exc}")

    result_text = str(payload.get("result", "")).strip()
    if json_schema is not None:
        structured = payload.get("structured_output")
        if structured is None:
            try:
                structured = json.loads(result_text)
            except json.JSONDecodeError as exc:
                return AIResult(ok=False, error=f"Respuesta inesperada de 'claude': {exc}")
        return AIResult(ok=True, text=result_text, payload=structured)

    if not result_text:
        return AIResult(ok=False, error="La IA no devolvió ninguna respuesta.")
    return AIResult(ok=True, text=result_text)


def run_isolated_prompt(
    prompt: str, system_prompt: str, model: str, timeout: int, cwd: Optional[str] = None,
) -> AIResult:
    """Llamada aislada de texto libre (Etapa 2 -- ver isolated_prompt.py
    para el aislamiento real: system prompt
    restrictivo, sin tools, carpeta de trabajo vacia). `cwd` solo aplica al
    backend 'claude' (aislamiento de filesystem); Gemini es una llamada de
    API pura, sin acceso a filesystem en ningun caso."""
    if active_provider() == PROVIDER_GEMINI:
        return _gemini_request(prompt, system_prompt, timeout, json_schema=None)
    return _claude_cli_request(prompt, system_prompt, model, timeout, json_schema=None, cwd=cwd)


def run_json_schema_prompt(prompt: str, json_schema: dict, model: str, timeout: int) -> AIResult:
    """Llamada de generacion de cuestionarios (Etapas 3/4/5 -- ver
    challenge_solver.py) restringida a un JSON Schema. `AIResult.payload`
    ya viene parseado (dict), listo para leer sin volver a hacer
    json.loads."""
    if active_provider() == PROVIDER_GEMINI:
        return _gemini_request(prompt, "", timeout, json_schema=json_schema)
    return _claude_cli_request(prompt, "", model, timeout, json_schema=json_schema, cwd=None)
