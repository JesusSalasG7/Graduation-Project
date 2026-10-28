"""Pruebas del código del juego que recibe la IA en la Etapa 3.

Correr desde la raíz del proyecto:
    .venv/bin/python -m unittest discover -s graphic_interface/ai/tests -t graphic_interface
"""

import ast
import io
import re
import sys
import tokenize
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # graphic_interface/

from ai.challenge_context import HIDDEN_FUNCTIONS, build_code_context, sanitize_source  # noqa: E402
from ai.isolated_prompt import build_isolated_message  # noqa: E402
from content.challenges import CHALLENGES  # noqa: E402
from games.game_patch import _parse_location, _solution_function  # noqa: E402


def _challenge_function(context_text: str, relative_file: str, class_name, func_name) -> ast.AST:
    marker = f"### Archivo: {relative_file}\n```python\n"
    start = context_text.index(marker) + len(marker)
    source = context_text[start:context_text.index("\n```", start)]
    tree = ast.parse(source)
    scope = tree
    if class_name:
        scope = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == class_name)
    return next(n for n in scope.body if isinstance(n, ast.FunctionDef) and n.name == func_name), source


def _files(context_text: str) -> dict[str, str]:
    parts = re.split(r"### Archivo: (\S+)\n```python\n", context_text)
    return {parts[i]: parts[i + 1].rsplit("\n```", 1)[0] for i in range(1, len(parts), 2)}


class BuildCodeContextTest(unittest.TestCase):
    def test_challenge_function_is_only_a_bare_raise(self):
        for name, challenge in CHALLENGES.items():
            with self.subTest(game=name):
                context = build_code_context(challenge)
                relative_file, class_name, func_name = _parse_location(challenge.location)
                node, _source = _challenge_function(context.text, relative_file, class_name, func_name)
                self.assertEqual(len(node.body), 1)
                self.assertEqual(ast.unparse(node.body[0]), "raise NotImplementedError")

    def test_no_comments_or_docstrings_anywhere(self):
        for name, challenge in CHALLENGES.items():
            context = build_code_context(challenge)
            for path, source in _files(context.text).items():
                with self.subTest(game=name, file=path):
                    tokens = tokenize.generate_tokens(io.StringIO(source).readline)
                    self.assertFalse([t for t in tokens if t.type == tokenize.COMMENT])
                    for node in ast.walk(ast.parse(source)):
                        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                            self.assertFalse(
                                node.body and isinstance(node.body[0], ast.Expr)
                                and isinstance(node.body[0].value, ast.Constant)
                                and isinstance(node.body[0].value.value, str),
                            )
                    self.assertNotIn("TODO", source)

    def test_hidden_functions_are_removed(self):
        for game, by_file in HIDDEN_FUNCTIONS.items():
            files = _files(build_code_context(CHALLENGES[game]).text)
            for path, names in by_file.items():
                tree = ast.parse(files[path])
                defined = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
                for func in names:
                    with self.subTest(game=game, func=func):
                        self.assertNotIn(func, defined)
                        source = (Path(__file__).resolve().parents[3] / game / path).read_text(encoding="utf-8")
                        self.assertIn(f"def {func}(", source, "la función ya no existe: actualizar HIDDEN_FUNCTIONS")

    def test_excludes_tests_and_non_python_files(self):
        for name, challenge in CHALLENGES.items():
            with self.subTest(game=name):
                context = build_code_context(challenge)
                self.assertTrue(context.files)
                self.assertIn("main.py", context.files)
                for path in context.files:
                    self.assertTrue(path.endswith(".py"))
                    self.assertNotIn("tests", Path(path).parts)
                self.assertEqual(len(context.sha256), 64)

    def test_sanitize_keeps_code_and_drops_hints(self):
        source = (
            '"""Docstring del módulo con pistas."""\n'
            "class World:\n"
            "    def other(self):\n"
            '        """pista"""\n'
            "        # comentario con pista\n"
            "        return '# esto es un string, no un comentario'\n"
            "\n"
            "    def target(self) -> int:\n"
            "        # TODO: pista\n"
            "        raise NotImplementedError('pista en el mensaje')\n"
            "\n"
            "def solved_twin():\n"
            "    return 1\n"
        )
        clean = sanitize_source(source, challenge=("World", "target"), hidden_functions=("solved_twin",))
        self.assertNotIn("pista", clean)
        self.assertNotIn("solved_twin", clean)
        self.assertIn("'# esto es un string, no un comentario'", clean)
        self.assertIn("raise NotImplementedError", clean)


class IsolatedMessageTest(unittest.TestCase):
    def test_prompt_goes_after_the_code_and_statement_is_not_sent(self):
        challenge = CHALLENGES["Game-01"]
        context = build_code_context(challenge)
        message = build_isolated_message("  cuenta las manzanas  ", context)
        self.assertTrue(message.endswith("cuenta las manzanas"))
        self.assertLess(message.index("World"), message.index("Instrucciones del usuario"))
        self.assertNotIn(challenge.statement[:80], message)


class SolutionFunctionTest(unittest.TestCase):
    def test_prefers_the_function_named_like_the_challenge(self):
        code = (
            "def helper(x):\n"
            "    return x\n"
            "\n"
            "def count_apples_in_range(self) -> int:\n"
            "    return 3\n"
        )
        node = _solution_function("count_apples_in_range", code)
        self.assertEqual(ast.unparse(node.body[0]), "return 3")

    def test_falls_back_to_the_first_function(self):
        node = _solution_function("count_apples_in_range", "def contar(self):\n    return 2\n")
        self.assertEqual(node.name, "count_apples_in_range")


if __name__ == "__main__":
    unittest.main()
