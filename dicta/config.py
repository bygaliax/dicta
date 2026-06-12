"""Configuración: %APPDATA%\\dicta\\config.toml, creado desde config.example.toml."""
import os
import shutil
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

def _app_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", str(Path.home()))) / "dicta"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "dicta"
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "dicta"


APP_DIR = _app_dir()


@dataclass
class Config:
    model: str = "large-v3"
    language: str = "es"
    vocabulario: list[str] = field(default_factory=list)
    sonidos: bool = True
    paste_shortcut: str = "cmd+v" if sys.platform == "darwin" else "ctrl+v"
    hotkey_enabled: bool = False
    hotkey_combo: str = "ctrl+alt+v"
    manos_libres_activado: bool = True
    wake_word: str = "claude"
    wake_confianza: float = 0.85
    silencio_segundos: float = 2.0
    auto_enviar: bool = True


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
    ml = data.get("manos_libres", {})
    cfg.model = w.get("model", cfg.model)
    cfg.language = w.get("language", cfg.language)
    cfg.vocabulario = list(w.get("vocabulario", cfg.vocabulario))
    cfg.sonidos = bool(ui.get("sonidos", cfg.sonidos))
    cfg.paste_shortcut = iny.get("paste_shortcut", cfg.paste_shortcut)
    cfg.hotkey_enabled = bool(hk.get("enabled", cfg.hotkey_enabled))
    cfg.hotkey_combo = hk.get("combo", cfg.hotkey_combo)
    cfg.manos_libres_activado = bool(ml.get("activado", cfg.manos_libres_activado))
    cfg.wake_word = str(ml.get("palabra", cfg.wake_word)).strip().lower()
    cfg.wake_confianza = float(ml.get("confianza", cfg.wake_confianza))
    cfg.silencio_segundos = float(ml.get("silencio_segundos", cfg.silencio_segundos))
    cfg.auto_enviar = bool(ml.get("auto_enviar", cfg.auto_enviar))
    return cfg


def ensure_config(example: Path, path: Path | None = None) -> Path:
    """Crea config.toml desde el ejemplo si no existe. Nunca sobrescribe."""
    path = path or APP_DIR / "config.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        shutil.copy(example, path)
    return path
