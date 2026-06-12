# tests/test_config.py
from pathlib import Path

from dicta.config import Config, ensure_config, load_config

SAMPLE = """
[whisper]
model = "small"
language = "es"
vocabulario = ["Netlify", "deploy"]

[ui]
sonidos = false

[inyeccion]
paste_shortcut = "ctrl+shift+v"

[hotkey]
enabled = true
combo = "ctrl+alt+d"
"""


def test_defaults_cuando_no_existe(tmp_path: Path):
    cfg = load_config(tmp_path / "no-existe.toml")
    assert cfg.model == "large-v3"
    assert cfg.language == "es"
    assert cfg.vocabulario == []
    assert cfg.sonidos is True
    assert cfg.paste_shortcut == "ctrl+v"
    assert cfg.hotkey_enabled is False


def test_parsea_toml(tmp_path: Path):
    p = tmp_path / "config.toml"
    p.write_text(SAMPLE, encoding="utf-8")
    cfg = load_config(p)
    assert cfg.model == "small"
    assert cfg.vocabulario == ["Netlify", "deploy"]
    assert cfg.sonidos is False
    assert cfg.paste_shortcut == "ctrl+shift+v"
    assert cfg.hotkey_enabled is True
    assert cfg.hotkey_combo == "ctrl+alt+d"


def test_toml_parcial_usa_defaults(tmp_path: Path):
    p = tmp_path / "config.toml"
    p.write_text('[whisper]\nmodel = "medium"\n', encoding="utf-8")
    cfg = load_config(p)
    assert cfg.model == "medium"
    assert cfg.paste_shortcut == "ctrl+v"


def test_ensure_config_copia_ejemplo_una_vez(tmp_path: Path):
    example = tmp_path / "config.example.toml"
    example.write_text(SAMPLE, encoding="utf-8")
    target = tmp_path / "appdata" / "config.toml"
    ensure_config(example, target)
    assert target.exists()
    target.write_text('[whisper]\nmodel = "editado"\n', encoding="utf-8")
    ensure_config(example, target)  # no debe sobrescribir
    assert load_config(target).model == "editado"


def test_toml_corrupto_usa_defaults(tmp_path: Path):
    p = tmp_path / "config.toml"
    p.write_text("esto no es toml [[[", encoding="utf-8")
    cfg = load_config(p)
    assert cfg.model == "large-v3"


def test_manos_libres_defaults_sin_seccion(tmp_path: Path):
    p = tmp_path / "config.toml"
    p.write_text("[ui]\nsonidos = true\n", encoding="utf-8")
    cfg = load_config(p)
    assert cfg.manos_libres_activado is True
    assert cfg.wake_word == "claude"
    assert cfg.silencio_segundos == 2.0
    assert cfg.auto_enviar is True


def test_manos_libres_personalizado(tmp_path: Path):
    p = tmp_path / "config.toml"
    p.write_text(
        '[manos_libres]\nactivado = false\npalabra = "Compu"\n'
        "silencio_segundos = 1.5\nauto_enviar = false\n",
        encoding="utf-8",
    )
    cfg = load_config(p)
    assert cfg.manos_libres_activado is False
    assert cfg.wake_word == "compu"  # normalizada a minúsculas
    assert cfg.silencio_segundos == 1.5
    assert cfg.auto_enviar is False
