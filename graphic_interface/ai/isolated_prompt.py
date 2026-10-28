"""Llamada aislada a la IA (backend configurable -- ver ai_backend.py):
el mecanismo real detrás del prompt que escribe el participante en la
Etapa 3 de la sesión guiada (ver challenge_solver.generate_isolated_
response).

Qué ve la IA: el código Python completo del juego del desafío actual (ver
challenge_context.build_code_context: sin tests, sin guías .md y con la
función del desafío sin su TODO) y, después, el texto exacto que escribió
el participante. Lo único que NO ve es el enunciado: lo que hay que lograr
lo sabe solo por las instrucciones del participante.

Por defecto usa el CLI `claude` (headless, `-p`) en vez de la API directa
de Anthropic, para no depender de una ANTHROPIC_API_KEY: el CLI ya
funciona con el login / suscripción que este equipo ya tiene configurado.
Alternativamente, con AI_PROVIDER=gemini + GEMINI_API_KEY (ver
ai_backend.py), la misma llamada se hace contra la API de Gemini.

  1. Aislamiento: el código del juego va DENTRO del mensaje (no se le da
     acceso a archivos). Con el CLI, `--tools ""` deshabilita toda
     herramienta y el proceso corre en una carpeta temporal vacía, para
     que no se autodescubra ningún CLAUDE.md ni configuración de este
     repositorio. El mensaje va por stdin: el código de algunos juegos
     supera el límite de largo de un argumento de línea de comandos.
  2. Determinismo: el CLI `claude` NO EXPONE un flag de temperature. Este
     requisito no se puede cumplir de forma estricta por esta vía -- es la
     contrapartida de evitar la API directa y no manejar una API key.
  3. System prompt: `--system-prompt` REEMPLAZA por completo el system
     prompt por defecto del agente (ver ISOLATED_SYSTEM_PROMPT): seguir
     solo las instrucciones del participante, usar el código para conocer
     los nombres reales, devolver solo código, y SIEMPRE devolver código
     aunque las instrucciones sean incompletas -- si les falta algo, eso se
     ve en el código que genera (y lo evalúan las Etapas 4/5 contra el
     enunciado). Con Gemini, ese mismo texto se manda como
     systemInstruction (ver ai_backend._gemini_request).
"""

import tempfile
from dataclasses import dataclass
from typing import Optional

from ai import ai_backend
from ai.challenge_context import CodeContext

ISOLATED_MODEL = "sonnet"
# Más alto que antes de mandar el código del juego: el mensaje ahora pesa
# entre 25 y 95 KB según el juego.
ISOLATED_TIMEOUT_SECONDS = 180


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
    "Eres un asistente de programación. Vas a recibir el código fuente "
    "completo de un proyecto en Python y, después, las instrucciones de un "
    "usuario. No tienes ningún otro contexto: lo que el usuario quiere "
    "lograr lo sabes única y exclusivamente por sus instrucciones. Usa el "
    "código para conocer los nombres, clases, métodos y estructuras que "
    "existen, pero haz solo lo que las instrucciones piden, de forma "
    "literal, sin agregar requisitos que no pidan ni suponer objetivos que "
    "no estén escritos en ellas. "
    "Tu respuesta debe ser ÚNICAMENTE código Python: solo la función o el "
    "método que escribas o modifiques (no el archivo completo ni el resto "
    "del proyecto), sin explicaciones antes o después, sin comentarios "
    "dentro del código, y sin bloques de markdown (```) -- solo el código "
    "en sí, listo para copiar y pegar. "
    "Responde SIEMPRE con código, aunque las instrucciones sean incompletas "
    "o ambiguas: en ese caso escribe la mejor implementación que puedas a "
    "partir de lo que las instrucciones dicen literalmente."
)


def build_isolated_message(participant_prompt: str, code_context: Optional[CodeContext]) -> str:
    """Mensaje que recibe la IA: el código del juego (si hay) y, al final,
    las instrucciones del participante tal cual las escribió."""
    prompt = participant_prompt.strip()
    if code_context is None or not code_context.text:
        return prompt
    return (
        "Este es el código fuente completo del proyecto:\n\n"
        f"{code_context.text}\n\n"
        "---\n\n"
        "Instrucciones del usuario:\n\n"
        f"{prompt}"
    )


@dataclass
class IsolatedPromptResult:
    ok: bool
    text: str = ""  # el código extraído: lo que ve el participante y se aplica al juego
    error: str = ""
    # Solo para el registro de la sesión (ver stage_capture.write_stage3_ai_files):
    raw_text: str = ""  # la respuesta completa tal cual llegó, antes de extraer el código
    model: str = ""  # modelo exacto que informó el proveedor, si lo informó


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


def ask_isolated_prompt(
    participant_prompt: str, code_context: Optional[CodeContext] = None,
) -> IsolatedPromptResult:
    """Envía `participant_prompt`, junto con el código del juego
    (`code_context`, ver challenge_context.py), al backend de IA
    seleccionado (ver ai_backend.py), con el system prompt de arriba, sin
    herramientas, y (para el backend 'claude') corriendo en una carpeta
    vacía para que no se cuele otro contexto de este proyecto.
    """
    prompt = participant_prompt.strip()
    if not prompt:
        return IsolatedPromptResult(ok=False, error="Escribe un prompt antes de enviarlo.")

    with tempfile.TemporaryDirectory(prefix="isolated_prompt_") as empty_dir:
        result = ai_backend.run_isolated_prompt(
            build_isolated_message(prompt, code_context), ISOLATED_SYSTEM_PROMPT,
            ISOLATED_MODEL, ISOLATED_TIMEOUT_SECONDS, cwd=empty_dir,
        )

    if not result.ok:
        return IsolatedPromptResult(ok=False, error=result.error, raw_text=result.raw_text, model=result.model)

    text = _strip_code_fences(result.text).strip()
    if not text:
        return IsolatedPromptResult(
            ok=False, error="La IA no devolvió ninguna respuesta.", raw_text=result.raw_text, model=result.model,
        )

    return IsolatedPromptResult(ok=True, text=text, raw_text=result.raw_text, model=result.model)
