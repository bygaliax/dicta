"""Cola de habla: los hooks de Claude Code dejan archivos JSON en
%APPDATA%\\dicta\\speak\\ y aquí se drenan y traducen a (texto, abre_mic).
Coalescing: si se acumulan cierres atrasados solo se habla el último;
los avisos/permisos se conservan todos, en orden."""
import json
from dataclasses import dataclass
from pathlib import Path

from dicta.speech_text import es_pregunta, ultimo_parrafo

KINDS = ("aviso", "permiso", "cierre")


@dataclass
class SpeakItem:
    kind: str
    text: str


def drenar_cola(speak_dir: Path) -> list[SpeakItem]:
    """Lee por orden de nombre y borra SIEMPRE (también corruptos)."""
    if not speak_dir.is_dir():
        return []
    items: list[SpeakItem] = []
    for f in sorted(speak_dir.glob("*.json")):
        try:
            # utf-8-sig: Set-Content -Encoding utf8 de PowerShell 5.1 mete BOM
            data = json.loads(f.read_text(encoding="utf-8-sig"))
            kind = str(data.get("kind", ""))
            text = str(data.get("text", "")).strip()
            if kind in KINDS and text:
                items.append(SpeakItem(kind, text))
        except Exception:
            pass
        finally:
            f.unlink(missing_ok=True)
    cierres = [i for i in items if i.kind == "cierre"]
    otros = [i for i in items if i.kind != "cierre"]
    return otros + cierres[-1:]


def preparar(
    items: list[SpeakItem],
    max_chars: int,
    leer_avisos: bool,
    leer_cierres: bool,
    escuchar_tras_pregunta: bool,
) -> list[tuple[str, bool]]:
    """(texto a hablar, abre_mic) por item. Permisos JAMÁS abren mic."""
    out: list[tuple[str, bool]] = []
    for it in items:
        if it.kind == "cierre":
            if not leer_cierres:
                continue
            texto = ultimo_parrafo(it.text, max_chars)
            if texto:
                out.append((texto, escuchar_tras_pregunta and es_pregunta(texto)))
        elif it.kind == "aviso":
            if leer_avisos:
                out.append((it.text, escuchar_tras_pregunta))
        else:  # "permiso"
            if leer_avisos:
                out.append((it.text, False))
    return out
