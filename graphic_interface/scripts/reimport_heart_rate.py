"""CLI para (re)procesar la frecuencia cardíaca de un desafío ya cerrado,
para cualquier participante/desafío -- sin pasar por la sesión guiada.

Casos de uso:
  - El desafío se cerró con "Siguiente juego" (esa pantalla no pide la
    carpeta del reloj, ver session_wizard._show_heart_rate_import) y el
    evaluador consigue el export después.
  - Ya se había cargado, pero se procesó con una versión anterior de
    slice_heart_rate (p.ej. antes de agregarse HEART_RATE_FALLBACK_
    TOLERANCE, o el soporte de medición continua vía JSON de binning en
    stage_capture.py) y hay que recortarlo de nuevo.

Uso:
    python graphic_interface/scripts/reimport_heart_rate.py --participante 1 --desafio 1 \\
        --carpeta "/ruta/a/samsunghealth_usuario_20260920151062"

`--carpeta` tiene que ser la carpeta COMPLETA que exporta Samsung Health
("Descargar mis datos personales"), no el CSV suelto -- el detalle minuto
a minuto de la medición continua vive en JSON aparte dentro de ella (ver
heart_rate_import.HEART_RATE_JSON_SUBDIR); con solo el CSV se pierden esas
lecturas y quedan únicamente los chequeos puntuales sueltos.

Requiere que las Etapas 2/3/4/5 de ese desafío ya esten exportadas (con su
sync_timeline.json) -- ver stage_capture.write_sync_timeline.
"""

import argparse
import sys
from pathlib import Path

# Script suelto: agrega graphic_interface/ al path para poder importar sus paquetes.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sensors.heart_rate_import import HeartRateValidationError, reimport_heart_rate_for_challenge  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reprocesa la frecuencia cardíaca del reloj para un desafío ya cerrado.",
    )
    parser.add_argument("--participante", type=int, required=True, help="Número de participante (ej. 1).")
    parser.add_argument("--desafio", type=int, required=True, help="Número de desafío (ej. 1).")
    parser.add_argument(
        "--carpeta", type=Path, required=True,
        help='Carpeta completa del export de Samsung Health (ej. "samsunghealth_usuario_<fecha>").',
    )
    args = parser.parse_args()

    try:
        warnings_by_stage = reimport_heart_rate_for_challenge(args.participante, args.desafio, args.carpeta)
    except (HeartRateValidationError, FileNotFoundError) as exc:
        print(f"Error: {exc}")
        raise SystemExit(1)

    for stage in sorted(warnings_by_stage):
        warnings = warnings_by_stage[stage]
        print(f"Etapa {stage}:")
        if warnings:
            for warning in warnings:
                print(f"  ⚠️  {warning}")
        else:
            print("  ✅  Lecturas encontradas dentro de la ventana de la etapa, sin advertencias.")


if __name__ == "__main__":
    main()
