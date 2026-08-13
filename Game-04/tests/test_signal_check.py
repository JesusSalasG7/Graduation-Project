"""
Direct tests of the verification rule itself, with no pygame/gale
involved at all -- src.signal_check is plain logic over a str.
"""
import pytest

from src.signal_check import is_stable_signal


@pytest.mark.parametrize(
    "text",
    ["RADAR", "RECONOCER", "SOMETEMOS", "ANILINA", "ROTOR", "SALAS", "SOMOS", "SERES"],
)
def test_stable_words_are_detected(text):
    assert is_stable_signal(text) is True


@pytest.mark.parametrize(
    "text",
    ["CODIGO", "PYTHON", "JUEGO", "SISTEMAS", "VENTANA", "TELEFONO", "MENSAJE", "CIRCUITO"],
)
def test_altered_words_are_detected(text):
    assert is_stable_signal(text) is False


def test_return_type_is_bool():
    assert isinstance(is_stable_signal("RADAR"), bool)
    assert isinstance(is_stable_signal("CODIGO"), bool)


def test_empty_string_is_stable():
    assert is_stable_signal("") is True


def test_single_character_is_stable():
    assert is_stable_signal("A") is True


def test_does_not_mutate_its_argument():
    text = "RADAR"
    is_stable_signal(text)
    assert text == "RADAR"
