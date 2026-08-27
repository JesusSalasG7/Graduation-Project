"""Punto de entrada del panel grafico del experimento (lanzador + participantes)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import main  # noqa: E402

if __name__ == "__main__":
    main()
