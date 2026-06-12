"""Configuración: %APPDATA%\\dicta\\config.toml, creado desde config.example.toml."""
import os
import shutil
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
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    w = data.get("whisper", {})
    ui = data.get("ui", {})
    iny = data.get("inyeccion", {})
    hk = data.get("hotkey", {})
    return Config(
        model=w.get("model", "large-v3"),
        language=w.get("language", "es"),
        vocabulario=list(w.get("vocabulario", [])),
        sonidos=bool(ui.get("sonidos", True)),
        paste_shortcut=iny.get("paste_shortcut", "ctrl+v"),
        hotkey_enabled=bool(hk.get("enabled", False)),
        hotkey_combo=hk.get("combo", "ctrl+alt+v"),
    )


def ensure_config(example: Path, path: Path | None = None) -> Path:
    """Crea config.toml desde el ejemplo si no existe. Nunca sobrescribe."""
    path = path or APP_DIR / "config.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        shutil.copy(example, path)
    return path
