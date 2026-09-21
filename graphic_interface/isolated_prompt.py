"""Llamada aislada al CLI `claude` (headless, `-p`): el mecanismo real
detras del prompt que escribe el participante en la Etapa 2 de la sesion
guiada (ver challenge_solver.generate_isolated_response), "hoja en blanco",
sin nada mas que el texto exacto que escribio.

Se usa el CLI en vez de la API directa de Anthropic a proposito, para no
depender de una ANTHROPIC_API_KEY: el CLI ya funciona con el login /
suscripcion que este equipo ya tiene configurado. La contrapartida es que
el aislamiento no es tan estricto como con la API (ver el punto 2):

  1. Aislamiento: se invoca `claude -p` pasandole UNICAMENTE el texto que
     escribio el participante -- sin enunciado, sin el juego, sin historial
     de la sesion -- y corriendo con el directorio de trabajo apuntando a
     una carpeta temporal vacia (no la de este proyecto), para que no se
     autodescubra ningun CLAUDE.md ni configuracion de este repositorio.
     `--tools ""` deshabilita toda herramienta (no puede leer/escribir
     archivos ni ejecutar nada).
  2. Determinismo: el CLI `claude` NO EXPONE un flag de temperature
     (verificado contra `claude -p --help`: no existe). Este requisito no
     se puede cumplir de forma estricta por esta via -- es la contrapartida
     de evitar la API directa (que si permite fijarla) y no manejar una
     ANTHROPIC_API_KEY.
  3. System prompt: `--system-prompt` REEMPLAZA por completo el system
     prompt por defecto del agente (a diferencia de `--append-system-
     prompt`, que solo le agrega texto encima), con el texto pedido para
     el estudio (ver ISOLATED_SYSTEM_PROMPT) mas dos clausulas agregadas:
     que la respuesta sea codigo puro (sin explicaciones ni comentarios), y
     que si no hay codigo posible (falta de contexto, o el prompt no pedia
     codigo) responda con la senal exacta NO_CODE en vez de texto libre --
     asi ask_isolated_prompt puede distinguir con certeza "no hubo
     respuesta valida" de "esto es la respuesta", sin tener que adivinar
     leyendo el texto.
"""

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass

CLAUDE_BIN = "claude"
ISOLATED_MODEL = "sonnet"
ISOLATED_TIMEOUT_SECONDS = 120


def claude_cli_available() -> bool:
    """True si el CLI `claude` esta instalado y en el PATH.

    Sin el, la sesion guiada NO se rompe -- ask_isolated_prompt/
    generate_response_quiz ya devuelven un error prolijo si intentan
    invocarlo igual (ver mas abajo) -- pero recien se enterarian de eso
    en la Etapa 3, despues de haber jugado las Etapas 1/2. Se usa para
    avisar ANTES de arrancar la sesion guiada (ver App.
    enter_session_wizard) a quien este probando la app sin Claude Code
    instalado, en vez de dejar que lo descubra a mitad de una sesion."""
    return shutil.which(CLAUDE_BIN) is not None

# Senal exacta que le pedimos al modelo devolver cuando NO puede producir
# codigo (por falta de contexto en el prompt, o porque el prompt no pedia
# codigo). Se detecta por igualdad exacta en ask_isolated_prompt para
# decidir si hay o no una respuesta valida -- mucho mas confiable que
# tratar de adivinar, leyendo el texto, si "esto es codigo o no".
NO_CODE_SENTINEL = "NO_CODE"

ISOLATED_SYSTEM_PROMPT = (
    "Eres un asistente de IA que inicia como una hoja en blanco. No tienes "
    "conocimiento de ningún contexto previo, sistema o problema subyacente. "
    "Debes responder única y exclusivamente basándote en la información y "
    "las instrucciones explícitas proporcionadas en el prompt del usuario. "
    "No asumas hechos, no inventes información (cero alucinaciones) y sé "
    "completamente literal con la solicitud. "
    "Tu respuesta debe ser ÚNICAMENTE código: sin explicaciones antes o "
    "después, sin comentarios dentro del código, y sin bloques de markdown "
    "(```) -- solo el código en sí, listo para copiar y pegar. "
    f"Si el prompt no pide generar código, o le falta el contexto "
    f"necesario para que puedas escribir código correcto (por ejemplo, no "
    f"dice qué función/firma implementar, o no describe el comportamiento "
    f"esperado), no inventes nada: respondé ÚNICAMENTE con el texto exacto "
    f"{NO_CODE_SENTINEL} (nada más, sin explicación)."
)


@dataclass
class IsolatedPromptResult:
    ok: bool
    text: str = ""
    error: str = ""


def _strip_code_fences(text: str) -> str:
    """Por si el modelo igual envuelve la respuesta en ```lang ... ```
    a pesar de la instruccion de no hacerlo -- lo saca para que quede
    codigo puro.
    """
    stripped = text.strip()
    if not stripped.startswith("```"):
        return text
    lines = stripped.splitlines()
    if len(lines) >= 2 and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1])
    return text


def ask_isolated_prompt(participant_prompt: str) -> IsolatedPromptResult:
    """Envia `participant_prompt` -- y solo eso -- al CLI `claude`, con el
    system prompt de arriba, sin herramientas, y corriendo en una carpeta
    vacia para minimizar que se cuele contexto de este proyecto.
    """
    prompt = participant_prompt.strip()
    if not prompt:
        return IsolatedPromptResult(ok=False, error="Escribe un prompt antes de enviarlo.")

    cmd = [
        CLAUDE_BIN, "-p", prompt,
        "--system-prompt", ISOLATED_SYSTEM_PROMPT,
        "--tools", "",
        "--model", ISOLATED_MODEL,
        "--output-format", "json",
    ]

    try:
        with tempfile.TemporaryDirectory(prefix="isolated_prompt_") as empty_dir:
            proc = subprocess.run(
                cmd, cwd=empty_dir, capture_output=True, text=True,
                timeout=ISOLATED_TIMEOUT_SECONDS,
            )
    except FileNotFoundError:
        return IsolatedPromptResult(ok=False, error="No se encontró el comando 'claude' en el PATH.")
    except subprocess.TimeoutExpired:
        return IsolatedPromptResult(
            ok=False, error=f"'claude' no respondió en {ISOLATED_TIMEOUT_SECONDS}s.",
        )

    if proc.returncode != 0:
        return IsolatedPromptResult(
            ok=False,
            error=f"'claude' terminó con error (código {proc.returncode}): {proc.stderr.strip()}",
        )

    text = proc.stdout.strip()
    try:
        payload = json.loads(proc.stdout)
        text = str(payload.get("result", text)).strip()
    except (json.JSONDecodeError, TypeError):
        pass

    text = _strip_code_fences(text).strip()
    if not text:
        return IsolatedPromptResult(ok=False, error="La IA no devolvió ninguna respuesta.")
    if text.strip(" `\n\t.") == NO_CODE_SENTINEL:
        return IsolatedPromptResult(
            ok=False,
            error="La IA no pudo generar código para este prompt (falta contexto o el "
            "prompt no pedía código).",
        )

    return IsolatedPromptResult(ok=True, text=text)
