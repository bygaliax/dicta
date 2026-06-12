"""Configuración: %APPDATA%\\dicta\\config.toml, creado desde config.example.toml."""
import os
import shutil
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

APP_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "dicta"


@dataclass
class Config:
    model: str = "large-v3"
    language: str = "es"
    vocabulario: list[str] = field(default_factory=list)
    sonidos: bool = True
    paste_shortcut: str = "ctrl+v"
    hotkey_enabled: bool = False
    hotkey_combo: str = "ctrl+alt+v"


def load_config(path: Path | None = None) -> Config:
    path = path or APP_DIR / "config.toml"
    if not path.exists():
        return Config()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        print(f"config.toml inválido ({exc}); usando defaults.", file=sys.stderr)
        return Config()

    cfg = Config()
    w = data.get("whisper", {})
    ui = data.get("ui", {})
    iny = data.get("inyeccion", {})
    hk = data.get("hotkey", {})
    cfg.model = w.get("model", cfg.model)
    cfg.language = w.get("language", cfg.language)
    cfg.vocabulario = list(w.get("vocabulario", cfg.vocabulario))
    cfg.sonidos = bool(ui.get("sonidos", cfg.sonidos))
    cfg.paste_shortcut = iny.get("paste_shortcut", cfg.paste_shortcut)
    cfg.hotkey_enabled = bool(hk.get("enabled", cfg.hotkey_enabled))
    cfg.hotkey_combo = hk.get("combo", cfg.hotkey_combo)
    return cfg


def ensure_config(example: Path, path: Path | None = None) -> Path:
    """Crea config.toml desde el ejemplo si no existe. Nunca sobrescribe."""
    path = path or APP_DIR / "config.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        shutil.copy(example, path)
    return path
