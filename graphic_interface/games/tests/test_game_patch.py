"""Pruebas del parche de la Etapa 6 (game_patch._apply_solution).

Correr desde la raíz del proyecto:
    .venv/bin/python -m unittest discover -s graphic_interface/games/tests -t graphic_interface
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # graphic_interface/

from games.game_patch import _apply_solution  # noqa: E402

MODULE_SOURCE = '''"""Docstring del módulo."""
from __future__ import annotations

LIMIT = 1


def solve(values):
    raise NotImplementedError


def other():
    return "intacta"
'''

CLASS_SOURCE = '''class World:
    def __init__(self):
        self.values = [1, 2, 3]

    def count(self):
        raise NotImplementedError

    def _passes(self, value):
        return value > 1
'''


def _patch(source: str, location: tuple, solution: str) -> dict:
    """Aplica `solution` sobre `source` en un archivo temporal y devuelve
    el espacio de nombres del módulo resultante."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "mod.py"
        path.write_text(source, encoding="utf-8")
        class_name, func_name = location
        _apply_solution(Path(tmp), "mod.py", class_name, func_name, solution)
        namespace: dict = {}
        exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), namespace)
        return namespace


class ApplySolutionTest(unittest.TestCase):
    def test_helper_functions_are_inserted(self):
        solution = (
            "def _double(x):\n    return x * 2\n\n"
            "def solve(values):\n    return [_double(v) for v in values]\n"
        )
        ns = _patch(MODULE_SOURCE, (None, "solve"), solution)
        self.assertEqual(ns["solve"]([1, 2]), [2, 4])
        self.assertEqual(ns["other"](), "intacta")

    def test_constants_and_imports_are_carried(self):
        solution = (
            "import math\nOFFSET = 10\n\n"
            "def solve(values):\n    return math.floor(sum(values) + OFFSET + LIMIT)\n"
        )
        ns = _patch(MODULE_SOURCE, (None, "solve"), solution)
        self.assertEqual(ns["solve"]([1.5]), 12)

    def test_existing_helper_is_replaced_not_duplicated(self):
        solution = "def other():\n    return 'nueva'\n\ndef solve(values):\n    return other()\n"
        ns = _patch(MODULE_SOURCE, (None, "solve"), solution)
        self.assertEqual(ns["solve"]([]), "nueva")

    def test_method_with_helper_method(self):
        solution = (
            "def _big(self, v):\n    return v >= 2\n\n"
            "def count(self):\n    return sum(1 for v in self.values if self._big(v))\n"
        )
        ns = _patch(CLASS_SOURCE, ("World", "count"), solution)
        self.assertEqual(ns["World"]().count(), 2)

    def test_method_wrapped_in_its_class(self):
        solution = (
            "class World:\n    def count(self):\n"
            "        return sum(1 for v in self.values if self._passes(v))\n"
        )
        ns = _patch(CLASS_SOURCE, ("World", "count"), solution)
        self.assertEqual(ns["World"]().count(), 2)

    def test_single_function_with_other_name_is_renamed(self):
        ns = _patch(MODULE_SOURCE, (None, "solve"), "def resolver(values):\n    return len(values)\n")
        self.assertEqual(ns["solve"]([1, 2, 3]), 3)
        self.assertNotIn("resolver", ns)


if __name__ == "__main__":
    unittest.main()
