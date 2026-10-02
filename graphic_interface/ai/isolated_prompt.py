"""Llamada aislada a la IA (backend configurable -- ver ai_backend.py):
el mecanismo real detrás del prompt que escribe el participante en la
Etapa 2 de la sesión guiada (ver challenge_solver.generate_isolated_
response), "hoja en blanco", sin nada más que el texto exacto que escribió.

Por defecto usa el CLI `claude` (headless, `-p`) en vez de la API directa
de Anthropic, para no depender de una ANTHROPIC_API_KEY: el CLI ya
funciona con el login / suscripción que este equipo ya tiene configurado.
Alternativamente, con AI_PROVIDER=gemini + GEMINI_API_KEY (ver
ai_backend.py), la misma llamada aislada se hace contra la API de Gemini.
La contrapartida del CLI (backend por defecto) es que el aislamiento no es
tan estricto como con una API directa (ver el punto 2):

  1. Aislamiento: se invoca `claude -p` pasándole ÚNICAMENTE el texto que
     escribió el participante -- sin enunciado, sin el juego, sin historial
     de la sesión -- y corriendo con el directorio de trabajo apuntando a
     una carpeta temporal vacía (no la de este proyecto), para que no se
     autodescubra ningún CLAUDE.md ni configuración de este repositorio.
     `--tools ""` deshabilita toda herramienta (no puede leer/escribir
     archivos ni ejecutar nada). Con el backend Gemini esto no aplica: es
     una llamada de API pura, sin acceso a filesystem en ningún caso.
  2. Determinismo: el CLI `claude` NO EXPONE un flag de temperature
     (verificado contra `claude -p --help`: no existe). Este requisito no
     se puede cumplir de forma estricta por esta vía -- es la contrapartida
     de evitar la API directa (que si permite fijarla) y no manejar una
     ANTHROPIC_API_KEY.
  3. System prompt: `--system-prompt` REEMPLAZA por completo el system
     prompt por defecto del agente (a diferencia de `--append-system-
     prompt`, que solo le agrega texto encima), con el texto pedido para
     el estudio (ver ISOLATED_SYSTEM_PROMPT) más dos cláusulas agregadas:
     que la respuesta sea código puro (sin explicaciones ni comentarios), y
     que SIEMPRE devuelva código, aunque el prompt sea incompleto o ambiguo
     -- si al prompt le falta contexto, eso se ve en el código que genera
     (y lo evaluan las Etapas 4/5 contra el enunciado), en vez de cortar
     la sesión en la Etapa 3. Con Gemini, ese mismo texto se manda como
     systemInstruction (ver ai_backend._gemini_request).
"""

import tempfile
from dataclasses import dataclass

from ai import ai_backend
ISOLATED_MODEL = "sonnet"
ISOLATED_TIMEOUT_SECONDS = 120


def ai_provider_available() -> bool:
    """True si el backend de IA actualmente seleccionado (ver
    ai_backend.active_provider) está listo para usarse.

    Sin el, la sesión guiada NO se rompe -- ask_isolated_prompt/
    generate_response_quiz ya devuelven un error prolijo si intentan
    invocarlo igual (ver más abajo) -- pero recién se enterarían de eso
    en la Etapa 3, después de haber jugado las Etapas 1/2. Se usa para
    avisar ANTES de arrancar la sesión guiada (ver App.
    enter_session_wizard) a quien este probando la app sin el backend
    configurado, en vez de dejar que lo descubra a mitad de una sesión."""
    return ai_backend.provider_available()


ISOLATED_SYSTEM_PROMPT = (
    "Eres un asistente de IA que inicia como una hoja en blanco. No tienes "
    "conocimiento de ningún contexto previo, sistema o problema subyacente. "
    "Debes responder única y exclusivamente basándote en la información y "
    "las instrucciones explícitas proporcionadas en el prompt del usuario. "
    "No agregues requisitos que el prompt no pida y sé completamente "
    "literal con la solicitud. "
    "Tu respuesta debe ser ÚNICAMENTE código: sin explicaciones antes o "
    "después, sin comentarios dentro del código, y sin bloques de markdown "
    "(```) -- solo el código en sí, listo para copiar y pegar. "
    "Responde SIEMPRE con código, aunque el prompt sea incompleto o "
    "ambiguo: en ese caso escribe la mejor implementación que puedas a "
    "partir de lo que el prompt dice literalmente."
)


@dataclass
class IsolatedPromptResult:
    ok: bool
    text: str = ""
    error: str = ""


def _strip_code_fences(text: str) -> str:
    """Por si el modelo igual envuelve la respuesta en ```lang ... ```
    a pesar de la instrucción de no hacerlo -- lo saca para que quede
    código puro.
    """
    stripped = text.strip()
    if not stripped.startswith("```"):
        return text
    lines = stripped.splitlines()
    if len(lines) >= 2 and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1])
    return text


def ask_isolated_prompt(participant_prompt: str) -> IsolatedPromptResult:
    """Envía `participant_prompt` -- y solo eso -- al backend de IA
    seleccionado (ver ai_backend.py), con el system prompt de arriba, sin
    herramientas, y (para el backend 'claude') corriendo en una carpeta
    vacía para minimizar que se cuele contexto de este proyecto.
    """
    prompt = participant_prompt.strip()
    if not prompt:
        return IsolatedPromptResult(ok=False, error="Escribe un prompt antes de enviarlo.")

    with tempfile.TemporaryDirectory(prefix="isolated_prompt_") as empty_dir:
        result = ai_backend.run_isolated_prompt(
            prompt, ISOLATED_SYSTEM_PROMPT, ISOLATED_MODEL, ISOLATED_TIMEOUT_SECONDS, cwd=empty_dir,
        )

    if not result.ok:
        return IsolatedPromptResult(ok=False, error=result.error)

    text = _strip_code_fences(result.text).strip()
    if not text:
        return IsolatedPromptResult(ok=False, error="La IA no devolvió ninguna respuesta.")

    return IsolatedPromptResult(ok=True, text=text)
