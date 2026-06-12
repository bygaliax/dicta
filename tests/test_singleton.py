"""Tests para singleton.py — lectura de contador y lógica de auto-cierre."""
from pathlib import Path

from dicta.singleton import read_counter, should_exit


def test_counter_inexistente_es_none(tmp_path: Path):
    assert read_counter(tmp_path / "no-existe") is None


def test_counter_invalido_es_none(tmp_path: Path):
    p = tmp_path / "sessions.count"
    p.write_text("basura")
    assert read_counter(p) is None


def test_counter_valido(tmp_path: Path):
    p = tmp_path / "sessions.count"
    p.write_text("2\n")
    assert read_counter(p) == 2


def test_should_exit():
    # None = lanzado a mano sin hooks: nunca auto-salir
    assert should_exit(None) is False
    assert should_exit(2) is False
    assert should_exit(1) is False
    assert should_exit(0) is True
