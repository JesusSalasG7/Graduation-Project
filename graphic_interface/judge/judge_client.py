"""Llamada al modelo juez, por uno de dos caminos (ver JUDGE_PROVIDER en
judge_config.py):

- "api" (por defecto): SDK oficial de Anthropic, con temperatura 0.
- "cli": el CLI `claude` con la suscripción de Claude, para evaluar sin
  clave de API. No permite fijar la temperatura.

No reutiliza ai/ai_backend.py (la IA de la sesión guiada) a propósito: el
juez no debe compartir configuración con la IA que ven los participantes.

El paquete `anthropic` se importa recién al usarlo: el panel importa este
módulo al arrancar (por el botón "Evaluar prompts") y no debe dejar de abrir
en un equipo donde todavía no se instaló esa dependencia.
"""

import json
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass

from judge import judge_config

# Códigos HTTP que vale la pena reintentar: timeout, conflicto, límite de
# uso y cualquier error del servidor (incluye 529, "sobrecargado").
_RETRYABLE_STATUS = {408, 409, 429}


class JudgeFatalError(RuntimeError):
    """Error que va a repetirse en todas las llamadas (clave ausente o
    inválida, modelo inexistente, parámetro rechazado): detiene la corrida."""


@dataclass
class JudgeCallResult:
    ok: bool
    text: str = ""
    model: str = ""  # modelo exacto que informó la API
    input_tokens: int = 0
    output_tokens: int = 0
    stop_reason: str = ""
    error: str = ""


class CliJudgeClient:
    """Marca que las llamadas van por el CLI `claude` (no hay nada que
    conectar: cada llamada es un proceso nuevo)."""


def provider_available() -> bool:
    """True si el proveedor elegido está listo: clave de API configurada, o
    CLI `claude` instalado."""
    if judge_config.judge_provider() == judge_config.PROVIDER_CLI:
        return shutil.which(judge_config.CLAUDE_BIN) is not None
    return bool(judge_config.load_api_key())


def provider_unavailable_reason() -> str:
    if judge_config.judge_provider() == judge_config.PROVIDER_CLI:
        return "No se encontró el CLI 'claude' instalado en este equipo."
    return (
        f"No se encontró la variable {judge_config.ANTHROPIC_API_KEY_ENV}. Agrégala al archivo .env de la "
        f"raíz del proyecto (ver .env.example), o usa la suscripción de Claude con "
        f"{judge_config.JUDGE_PROVIDER_ENV}={judge_config.PROVIDER_CLI}."
    )


def provider_label() -> str:
    if judge_config.judge_provider() == judge_config.PROVIDER_CLI:
        return "suscripción de Claude (CLI, sin temperatura fija)"
    return f"API de Anthropic (temperatura {judge_config.JUDGE_TEMPERATURE})"


def create_client():
    if judge_config.judge_provider() == judge_config.PROVIDER_CLI:
        if not provider_available():
            raise JudgeFatalError(provider_unavailable_reason())
        return CliJudgeClient()
    try:
        import anthropic
    except ImportError as exc:
        raise JudgeFatalError(
            "Falta el paquete 'anthropic'. Instálalo con \"Reparar entorno\" o con "
            "pip install -r graphic_interface/requirements.txt."
        ) from exc
    api_key = judge_config.load_api_key()
    if not api_key:
        raise JudgeFatalError(provider_unavailable_reason())
    # max_retries=0: los reintentos los maneja call_judge, para que la
    # espera y la cantidad queden a la vista en judge_config.py.
    return anthropic.Anthropic(api_key=api_key, max_retries=0, timeout=judge_config.JUDGE_TIMEOUT_SECONDS)


def _retry_wait(attempt: int, exc: Exception) -> float:
    """Lo que pida la API en `retry-after`, o espera exponencial."""
    response = getattr(exc, "response", None)
    header = response.headers.get("retry-after") if response is not None else None
    try:
        wait = float(header)
    except (TypeError, ValueError):
        wait = judge_config.JUDGE_RETRY_BASE_SECONDS * (2 ** attempt)
    return min(max(wait, 0.0), judge_config.JUDGE_RETRY_MAX_SECONDS)


def call_judge(client, prompt_text: str, sleep=time.sleep) -> JudgeCallResult:
    """Una evaluación: un único mensaje de usuario, sin system prompt ni
    historial. Reintenta ante errores transitorios; si se agotan los
    reintentos devuelve ok=False para que la corrida siga con el resto."""
    if isinstance(client, CliJudgeClient):
        return _call_judge_cli(prompt_text, sleep)
    import anthropic

    last_error = ""
    for attempt in range(judge_config.JUDGE_NETWORK_RETRIES + 1):
        try:
            response = client.messages.create(
                model=judge_config.judge_model(),
                max_tokens=judge_config.JUDGE_MAX_TOKENS,
                temperature=judge_config.JUDGE_TEMPERATURE,
                messages=[{"role": "user", "content": prompt_text}],
            )
        except anthropic.APIStatusError as exc:
            if exc.status_code not in _RETRYABLE_STATUS and exc.status_code < 500:
                raise JudgeFatalError(f"La API rechazó la llamada ({exc.status_code}): {exc.message}") from exc
            last_error, failure = f"Error {exc.status_code} de la API: {exc.message}", exc
        except anthropic.APIConnectionError as exc:  # incluye los timeouts
            last_error, failure = f"Error de red: {exc}", exc
        else:
            text = "".join(block.text for block in response.content if block.type == "text")
            return JudgeCallResult(
                ok=True, text=text, model=response.model,
                input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens,
                stop_reason=response.stop_reason or "",
            )
        if attempt < judge_config.JUDGE_NETWORK_RETRIES:
            sleep(_retry_wait(attempt, failure))
    return JudgeCallResult(ok=False, error=f"{last_error} (tras {judge_config.JUDGE_NETWORK_RETRIES} reintentos)")


def _cli_request(prompt_text: str) -> JudgeCallResult:
    """Un proceso `claude -p` por evaluación: sin herramientas, con el
    prompt por la entrada estándar y desde una carpeta temporal, para que el
    CLI no cargue el CLAUDE.md ni la memoria de este proyecto."""
    cmd = [
        judge_config.CLAUDE_BIN, "-p", "--tools", "", "--model", judge_config.judge_model(),
        "--output-format", "json", "--system-prompt", judge_config.JUDGE_CLI_SYSTEM_PROMPT,
    ]
    try:
        proc = subprocess.run(
            cmd, input=prompt_text, cwd=tempfile.gettempdir(), capture_output=True, text=True,
            timeout=judge_config.JUDGE_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        raise JudgeFatalError("No se encontró el comando 'claude' en el PATH.") from exc
    except subprocess.TimeoutExpired:
        return JudgeCallResult(ok=False, error=f"'claude' no respondió en {judge_config.JUDGE_TIMEOUT_SECONDS:.0f}s")

    try:
        payload = json.loads(proc.stdout)
    except (json.JSONDecodeError, TypeError):
        payload = None
    if not isinstance(payload, dict):
        detail = (proc.stderr or proc.stdout or "").strip()[:300]
        return JudgeCallResult(ok=False, error=f"'claude' terminó con error (código {proc.returncode}): {detail}")

    text = str(payload.get("result", ""))
    if proc.returncode != 0 or payload.get("is_error"):
        # Acá cae, entre otros, el aviso de límite de uso de la suscripción.
        return JudgeCallResult(ok=False, error=f"'claude' informó un error: {text[:300]}")

    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    model_usage = payload.get("modelUsage") if isinstance(payload.get("modelUsage"), dict) else {}
    # El CLI reparte la entrada entre tokens nuevos y de caché: se suman.
    input_tokens = sum(
        int(usage.get(key) or 0)
        for key in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
    )
    return JudgeCallResult(
        ok=True, text=text, model=", ".join(str(name) for name in model_usage),
        input_tokens=input_tokens, output_tokens=int(usage.get("output_tokens") or 0),
        stop_reason=str(payload.get("stop_reason") or ""),
    )


def _call_judge_cli(prompt_text: str, sleep=time.sleep) -> JudgeCallResult:
    """Mismos reintentos con espera creciente que por la API. Si se alcanzó
    el límite de uso de la suscripción los reintentos no alcanzan: la corrida
    se detiene sola (JUDGE_MAX_CONSECUTIVE_FAILURES) y se reanuda más tarde."""
    result = JudgeCallResult(ok=False)
    for attempt in range(judge_config.JUDGE_NETWORK_RETRIES + 1):
        result = _cli_request(prompt_text)
        if result.ok:
            return result
        if attempt < judge_config.JUDGE_NETWORK_RETRIES:
            sleep(min(judge_config.JUDGE_RETRY_BASE_SECONDS * (2 ** attempt), judge_config.JUDGE_RETRY_MAX_SECONDS))
    result.error += f" (tras {judge_config.JUDGE_NETWORK_RETRIES} reintentos)"
    return result
