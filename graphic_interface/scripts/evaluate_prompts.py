"""Evalúa con el juez (LLM-as-a-judge) los prompts del dataset sintético
data/dataset_prompts.json. Los resultados quedan en data/juez/dataset_sintetico/.

Por defecto usa la API de Anthropic (clave en la variable de entorno
ANTHROPIC_API_KEY o en el archivo .env de la raíz del proyecto). Con
JUDGE_PROVIDER=cli usa en cambio la suscripción de Claude a través del CLI
`claude`, sin clave, pero sin poder fijar la temperatura (ver
judge/judge_config.py). --estimar no llama al modelo en ningún caso.

Uso:
    .venv/bin/python graphic_interface/scripts/evaluate_prompts.py --estimar
    .venv/bin/python graphic_interface/scripts/evaluate_prompts.py --prueba 10
    .venv/bin/python graphic_interface/scripts/evaluate_prompts.py

Si el proceso se corta, volver a correrlo sigue desde donde quedó: no repite
las evaluaciones ya guardadas en llamadas.jsonl.
"""

import argparse
import sys
from pathlib import Path

# Script suelto: agrega graphic_interface/ al path para poder importar sus paquetes.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from judge import judge_client, judge_config, judge_runner  # noqa: E402
from judge.judge_inputs import JudgeInputError, load_dataset_prompts  # noqa: E402
from judge.judge_prompt import DIMENSIONS, GLOBAL_LEVEL, SCORE_KEYS, parse_reasoning  # noqa: E402


def print_estimate(records, results_dir: Path) -> None:
    estimate = judge_runner.estimate_run(records, results_dir)
    print(f"Modelo:               {judge_config.judge_model()}")
    print(f"Proveedor:            {judge_client.provider_label()}")
    print(f"Prompts:              {estimate['prompts']}")
    print(f"Repeticiones:         {judge_config.JUDGE_REPETITIONS}")
    print(f"Llamadas totales:     {estimate['llamadas_totales']}")
    saved = estimate['llamadas_totales'] - estimate['llamadas_pendientes']
    print(f"Llamadas pendientes:  {estimate['llamadas_pendientes']} ({saved} ya guardadas)")
    print(f"Tokens de entrada:    ~{estimate['tokens_entrada']:,} (aproximado: 1 token cada "
          f"{judge_config.JUDGE_CHARS_PER_TOKEN} caracteres)")
    print(f"Tokens de salida:     ~{estimate['tokens_salida']:,} (suponiendo "
          f"{judge_config.JUDGE_ESTIMATED_OUTPUT_TOKENS} por respuesta)")
    if estimate["costo_usd"] is None:
        print(f"Costo:                sin calcular -- define {judge_config.JUDGE_PRICE_INPUT_ENV} y "
              f"{judge_config.JUDGE_PRICE_OUTPUT_ENV} (USD por millón de tokens) con el precio vigente del modelo.")
    else:
        print(f"Costo aproximado:     USD {estimate['costo_usd']:.2f}")
    print("Estimación local: no se llamó a la API.")


def print_reasoning(records, results_dir: Path) -> None:
    """Para --prueba: el texto de cada prompt con la evidencia, el
    razonamiento y el puntaje que dio el juez en cada repetición."""
    last_valid = {}
    for call in judge_runner.read_calls(results_dir):
        if call.get("puntajes"):
            last_valid[(call["id"], call["repeticion"])] = call
    for record in records:
        print("\n" + "=" * 78)
        details = " · ".join(f"{key}: {value}" for key, value in record.extra.items())
        print(f"{record.id} · {record.desafio}" + (f" · {details}" if details else ""))
        print(f"Prompt: {record.prompt}")
        for repetition in range(1, judge_config.JUDGE_REPETITIONS + 1):
            call = last_valid.get((record.id, repetition))
            if call is None:
                print(f"\n  Repetición {repetition}: sin evaluación válida")
                continue
            scores = call["puntajes"]
            print(f"\n  Repetición {repetition}: " + "  ".join(f"{key}={scores[key]}" for key in SCORE_KEYS))
            reasoning = parse_reasoning(call["respuesta"])
            for name in DIMENSIONS:
                entry = reasoning.get("dimensiones", {}).get(name, {})
                print(f"    [{name}] {scores[name]}")
                print(f"      evidencia:    {entry.get('evidencia', '')}")
                print(f"      razonamiento: {entry.get('razonamiento', '')}")
            print(f"    [{GLOBAL_LEVEL}] {scores[GLOBAL_LEVEL]}")
            print(f"      justificación: {reasoning.get(GLOBAL_LEVEL, {}).get('justificacion', '')}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--prueba", type=int, metavar="N",
                       help="evalúa N prompts al azar y muestra los razonamientos del juez")
    group.add_argument("--estimar", action="store_true",
                       help="cuenta llamadas y tokens sin usar la API, para estimar el costo")
    args = parser.parse_args()

    results_dir = judge_config.results_dir(judge_config.SOURCE_SYNTHETIC)
    try:
        records = load_dataset_prompts()
        if args.prueba is not None:
            records = judge_runner.sample_records(records, args.prueba)
        if args.estimar:
            print_estimate(records, results_dir)
            return 0
        if not judge_client.provider_available():
            print(judge_client.provider_unavailable_reason())
            return 1

        def on_progress(done: int, total: int, error: str) -> None:
            if error:
                print(f"\n  ⚠️  {error}")
            print(f"\rEvaluados: {done} / {total}", end="", flush=True)

        print(f"Juez: {judge_config.judge_model()} · {judge_client.provider_label()} · "
              f"{judge_config.JUDGE_REPETITIONS} repeticiones · plantilla v{judge_config.JUDGE_TEMPLATE_VERSION}")
        summary = judge_runner.run_judge(records, results_dir=results_dir, on_progress=on_progress)
    except JudgeInputError as exc:
        print(f"Error en los archivos de entrada: {exc}")
        return 1

    print()
    if args.prueba is not None:
        print_reasoning(records, results_dir)
        print()
    print(f"Prompts con todas las repeticiones válidas: {summary.evaluated_prompts} / {summary.total_prompts}")
    print(f"Llamadas hechas en esta corrida: {summary.calls_made}")
    print(f"Errores: {len(summary.errors)}")
    print(f"Registro de llamadas: {judge_runner.calls_path(results_dir)}")
    print(f"Resultados:           {summary.results_path}")
    if summary.aborted:
        print(f"⚠️  La corrida no terminó: {summary.aborted}")
        print("   Vuelve a ejecutar el mismo comando para continuar desde donde quedó.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
