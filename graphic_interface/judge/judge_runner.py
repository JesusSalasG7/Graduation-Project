"""Orquestador del juez: decide qué falta evaluar, hace las llamadas, las
registra y arma el CSV de resultados.

Lo usan por igual la terminal (scripts/evaluate_prompts.py) y el botón
"Evaluar prompts" de la pestaña Sesión (ui/app.py). Ningún paso de la sesión
guiada del participante importa este módulo.

Salidas, en la carpeta de resultados (data/juez/<origen>/):
- llamadas.jsonl: una línea por llamada a la API, se agrega al final a medida
  que llegan las respuestas. Es el registro crudo y la fuente de verdad.
- resultados.csv: una fila por prompt, se regenera entero desde el .jsonl.
"""

import csv
import json
import random
import statistics
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from judge import judge_client, judge_config
from judge.judge_client import JudgeFatalError
from judge.judge_inputs import PromptRecord
from judge.judge_prompt import (
    SCORE_KEYS, JudgeContext, build_judge_prompt, context_hash, load_judge_context, validate_judge_response,
)

# on_progress(prompts_evaluados, prompts_totales, error): `error` viene vacío
# salvo cuando una llamada falló.
ProgressCallback = Callable[[int, int, str], None]


@dataclass
class JudgeRunSummary:
    total_prompts: int = 0
    evaluated_prompts: int = 0  # con todas sus repeticiones válidas
    calls_made: int = 0
    errors: list[str] = field(default_factory=list)
    aborted: str = ""  # motivo, si la corrida se detuvo antes de terminar
    results_path: Optional[Path] = None


def calls_path(results_dir: Path) -> Path:
    return results_dir / judge_config.CALLS_FILE_NAME


def results_path(results_dir: Path) -> Path:
    return results_dir / judge_config.RESULTS_FILE_NAME


def read_calls(results_dir: Path) -> list[dict]:
    """Todas las líneas de llamadas.jsonl. Una línea cortada (proceso
    interrumpido justo al escribir) se ignora en vez de romper la lectura."""
    path = calls_path(results_dir)
    if not path.exists():
        return []
    calls = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                calls.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return calls


def _valid_scores(calls: list[dict], context: JudgeContext) -> dict[tuple[str, int], dict]:
    """{(id, repetición): puntajes} de las llamadas válidas hechas con la
    configuración ACTUAL (mismo proveedor, modelo, versión de plantilla y texto
    enviado). Lo evaluado con otra configuración queda en el .jsonl pero no
    cuenta: ni para reanudar ni para los resultados."""
    model = judge_config.judge_model()
    provider = judge_config.judge_provider()
    hashes: dict[str, str] = {}
    valid = {}
    for call in calls:
        if not call.get("puntajes") or call.get("modelo") != model:
            continue
        if call.get("proveedor", judge_config.PROVIDER_API) != provider:
            continue
        if call.get("version_plantilla") != judge_config.JUDGE_TEMPLATE_VERSION:
            continue
        challenge = call.get("desafio")
        if challenge not in context.specs:
            continue
        if challenge not in hashes:
            hashes[challenge] = context_hash(context, challenge)
        if call.get("hash_plantilla") != hashes[challenge]:
            continue
        valid[(call["id"], call["repeticion"])] = call["puntajes"]
    return valid


def pending_tasks(
    records: list[PromptRecord], context: JudgeContext, results_dir: Path,
) -> list[tuple[PromptRecord, int]]:
    """(prompt, repetición) que faltan, en orden aleatorio con semilla fija.
    Se mezcla la lista completa y recién después se quita lo ya evaluado,
    así el orden es el mismo se corte o no la corrida."""
    tasks = [
        (record, repetition)
        for record in records
        for repetition in range(1, judge_config.JUDGE_REPETITIONS + 1)
    ]
    random.Random(judge_config.JUDGE_SEED).shuffle(tasks)
    done = _valid_scores(read_calls(results_dir), context)
    return [(record, repetition) for record, repetition in tasks if (record.id, repetition) not in done]


def sample_records(records: list[PromptRecord], count: int) -> list[PromptRecord]:
    """N prompts al azar para --prueba, con la misma semilla (repetible)."""
    count = max(0, min(count, len(records)))
    return random.Random(judge_config.JUDGE_SEED).sample(records, count)


def estimate_run(records: list[PromptRecord], results_dir: Path) -> dict:
    """Llamadas y tokens aproximados SIN usar la API (los tokens se estiman
    por cantidad de caracteres; el conteo exacto solo lo da la API)."""
    context = load_judge_context()
    tasks = pending_tasks(records, context, results_dir)
    input_tokens = sum(
        len(build_judge_prompt(context, record.desafio, record.prompt)) / judge_config.JUDGE_CHARS_PER_TOKEN
        for record, _ in tasks
    )
    output_tokens = len(tasks) * judge_config.JUDGE_ESTIMATED_OUTPUT_TOKENS
    price_input, price_output = judge_config.token_prices()
    cost = None
    if price_input is not None and price_output is not None:
        cost = (input_tokens * price_input + output_tokens * price_output) / 1_000_000
    return {
        "prompts": len(records),
        "llamadas_totales": len(records) * judge_config.JUDGE_REPETITIONS,
        "llamadas_pendientes": len(tasks),
        "tokens_entrada": round(input_tokens),
        "tokens_salida": output_tokens,
        "costo_usd": cost,
    }


def run_judge(
    records: list[PromptRecord],
    *,
    results_dir: Optional[Path] = None,
    on_progress: Optional[ProgressCallback] = None,
    stop_event: Optional[threading.Event] = None,
    client=None,
) -> JudgeRunSummary:
    """Evalúa lo que falte de `records` y regenera resultados.csv.

    Se puede cortar en cualquier momento (cerrar la app, Ctrl+C, stop_event):
    cada respuesta se guarda apenas llega y la próxima corrida sigue desde ahí.
    `client` solo se pasa en las pruebas, para no llamar a la API real.
    """
    results_dir = results_dir or judge_config.results_dir()
    results_dir.mkdir(parents=True, exist_ok=True)
    stop_event = stop_event or threading.Event()
    context = load_judge_context()
    tasks = pending_tasks(records, context, results_dir)

    # El progreso se informa en prompts: uno cuenta cuando ya no le quedan
    # repeticiones pendientes.
    remaining: dict[str, int] = {}
    for record, _ in tasks:
        remaining[record.id] = remaining.get(record.id, 0) + 1
    summary = JudgeRunSummary(total_prompts=len(records))
    finished_prompts = len(records) - len(remaining)

    def report(error: str = "") -> None:
        if on_progress:
            on_progress(finished_prompts, len(records), error)

    report()
    if tasks:
        try:
            client = client or judge_client.create_client()
        except JudgeFatalError as exc:
            summary.aborted = str(exc)
            tasks = []

    write_lock = threading.Lock()
    model = judge_config.judge_model()

    def log_call(record: PromptRecord, repetition: int, attempt: int, result, scores, error: str) -> None:
        line = {
            "id": record.id,
            "desafio": record.desafio,
            "repeticion": repetition,
            "intento": attempt,
            "proveedor": judge_config.judge_provider(),
            "modelo": model,
            "modelo_respuesta": result.model,
            "version_plantilla": judge_config.JUDGE_TEMPLATE_VERSION,
            "hash_plantilla": context_hash(context, record.desafio),
            "temperatura": judge_config.judge_temperature(),
            "fecha": datetime.now().isoformat(timespec="seconds"),
            "tokens_entrada": result.input_tokens,
            "tokens_salida": result.output_tokens,
            "respuesta": result.text,
            "puntajes": scores,
            "error": error,
        }
        with write_lock, calls_path(results_dir).open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
            f.flush()
            summary.calls_made += 1

    def evaluate(record: PromptRecord, repetition: int) -> str:
        """Una repetición de un prompt. Devuelve "" si quedó un puntaje
        válido, o el error. Si la respuesta no cumple el formato se repite
        la llamada una vez; cada llamada queda registrada."""
        judge_prompt = build_judge_prompt(context, record.desafio, record.prompt)
        error = ""
        for attempt in range(1, judge_config.JUDGE_INVALID_RETRIES + 2):
            if stop_event.is_set():
                return "cancelado"
            result = judge_client.call_judge(client, judge_prompt)
            if not result.ok:
                log_call(record, repetition, attempt, result, None, result.error)
                return result.error  # ya se reintentó dentro de call_judge
            scores, error = validate_judge_response(result.text)
            if scores is None and result.stop_reason == "max_tokens":
                error += " (respuesta cortada por max_tokens)"
            log_call(record, repetition, attempt, result, scores, error)
            if scores is not None:
                return ""
        return error

    consecutive_failures = 0
    if tasks:
        with ThreadPoolExecutor(max_workers=judge_config.JUDGE_MAX_WORKERS) as executor:
            futures = {executor.submit(evaluate, record, repetition): (record, repetition) for record, repetition in tasks}
            try:
                for future in as_completed(futures):
                    record, repetition = futures[future]
                    try:
                        error = future.result()
                    except JudgeFatalError as exc:
                        summary.aborted = summary.aborted or str(exc)
                        stop_event.set()
                        continue
                    if error == "cancelado":
                        continue
                    remaining[record.id] -= 1
                    if remaining[record.id] == 0:
                        finished_prompts += 1
                    if error:
                        consecutive_failures += 1
                        message = f"{record.id} (repetición {repetition}): {error}"
                        summary.errors.append(message)
                        report(message)
                        if consecutive_failures >= judge_config.JUDGE_MAX_CONSECUTIVE_FAILURES:
                            summary.aborted = summary.aborted or (
                                f"Se detuvo tras {consecutive_failures} llamadas fallidas seguidas."
                            )
                            stop_event.set()
                    else:
                        consecutive_failures = 0
                        report()
            except KeyboardInterrupt:
                # Ctrl+C en la terminal: no se lanzan más llamadas y se
                # escribe el CSV con lo que haya.
                summary.aborted = "Interrumpido por el usuario."
                stop_event.set()
                executor.shutdown(wait=True, cancel_futures=True)

    if stop_event.is_set() and not summary.aborted:
        summary.aborted = "Cancelado."
    summary.results_path = write_results(records, results_dir, context)
    done = _valid_scores(read_calls(results_dir), context)
    summary.evaluated_prompts = sum(
        all((record.id, repetition) in done for repetition in range(1, judge_config.JUDGE_REPETITIONS + 1))
        for record in records
    )
    return summary


def _number(value: float):
    """La mediana de 3 enteros es entera; con 2 repeticiones puede dar x.5."""
    return int(value) if float(value).is_integer() else value


def write_results(records: list[PromptRecord], results_dir: Path, context: Optional[JudgeContext] = None) -> Path:
    """resultados.csv: una fila por prompt que tenga al menos una llamada,
    con los campos del dataset, la mediana de cada puntaje y la diferencia
    máxima entre repeticiones (máximo - mínimo). Se regenera entero a partir
    de llamadas.jsonl."""
    context = context or load_judge_context()
    calls = read_calls(results_dir)
    valid = _valid_scores(calls, context)
    attempted = {call.get("id") for call in calls}
    extra_fields = list(dict.fromkeys(key for record in records for key in record.extra))

    header = [
        "id", *extra_fields, "desafio", "prompt",
        *[f"{key}_mediana" for key in SCORE_KEYS],
        *[f"{key}_dif_max" for key in SCORE_KEYS],
        "dif_max", "repeticiones_validas", "repeticiones_identicas", "nivel_global_repeticiones",
        "proveedor", "modelo", "version_plantilla",
    ]
    path = results_path(results_dir)
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for record in records:
            if record.id not in attempted:
                continue
            repetitions = [
                valid[(record.id, repetition)]
                for repetition in range(1, judge_config.JUDGE_REPETITIONS + 1)
                if (record.id, repetition) in valid
            ]
            row = [record.id, *[record.extra.get(key, "") for key in extra_fields], record.desafio, record.prompt]
            if repetitions:
                spreads = [max(r[key] for r in repetitions) - min(r[key] for r in repetitions) for key in SCORE_KEYS]
                row += [_number(statistics.median(r[key] for r in repetitions)) for key in SCORE_KEYS]
                row += spreads
                row += [
                    max(spreads),
                    len(repetitions),
                    # Idénticas = los 6 puntajes iguales en TODAS las repeticiones configuradas.
                    int(len(repetitions) == judge_config.JUDGE_REPETITIONS and max(spreads) == 0),
                    "|".join(str(r["nivel_global"]) for r in repetitions),
                ]
            else:
                row += [""] * (2 * len(SCORE_KEYS)) + ["", 0, 0, ""]
            row += [judge_config.judge_provider(), judge_config.judge_model(), judge_config.JUDGE_TEMPLATE_VERSION]
            writer.writerow(row)
    tmp.replace(path)
    return path
