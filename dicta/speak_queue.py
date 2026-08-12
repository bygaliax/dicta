"""Cola de habla: los hooks de Claude Code dejan archivos JSON en
%APPDATA%\\dicta\\speak\\ y aquí se drenan y traducen a (kind, texto, abre_mic).
Coalescing en dos niveles: drenar_cola solo se queda con el último cierre
de un mismo drenado; encolar() extiende ese descarte entre ticks, para que
un cierre nuevo elimine los cierres viejos aún no hablados de la cola de
pendientes. Los avisos/permisos se conservan todos, en orden."""
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
    """Lee por orden de nombre y borra los archivos consumidos (también los
    corruptos). Si un hook todavía tiene el archivo abierto (Set-Content sin
    terminar), unlink() lanza PermissionError/OSError: no consumimos ese
    item (no se hace append) y se queda en disco para reintentarlo en el
    próximo tick, sin relectura duplicada ni crash del QTimer."""
    if not speak_dir.is_dir():
        return []
    items: list[SpeakItem] = []
    for f in sorted(speak_dir.glob("*.json")):
        try:
            # utf-8-sig: Set-Content -Encoding utf8 de PowerShell 5.1 mete BOM
            data = json.loads(f.read_text(encoding="utf-8-sig"))
            kind = str(data.get("kind", ""))
            text = str(data.get("text", "")).strip()
        except Exception:
            kind, text = "", ""
        try:
            f.unlink()
        except OSError:
            continue  # archivo bloqueado o ya borrado: no se consume ahora
        if kind in KINDS and text:
            items.append(SpeakItem(kind, text))
    cierres = [i for i in items if i.kind == "cierre"]
    otros = [i for i in items if i.kind != "cierre"]
    return otros + cierres[-1:]


def preparar(
    items: list[SpeakItem],
    max_chars: int,
    leer_avisos: bool,
    leer_cierres: bool,
    escuchar_tras_pregunta: bool,
) -> list[tuple[str, str, bool]]:
    """(kind, texto a hablar, abre_mic) por item. Permisos JAMÁS abren mic.
    Se conserva el kind para que encolar() pueda coalescer cierres entre
    ticks distintos del QTimer."""
    out: list[tuple[str, str, bool]] = []
    for it in items:
        if it.kind == "cierre":
            if not leer_cierres:
                continue
            texto = ultimo_parrafo(it.text, max_chars)
            if texto:
                out.append(("cierre", texto, escuchar_tras_pregunta and es_pregunta(texto)))
        elif it.kind == "aviso":
            if leer_avisos:
                out.append(("aviso", it.text, escuchar_tras_pregunta))
        else:  # "permiso"
            if leer_avisos:
                out.append(("permiso", it.text, False))
    return out


def encolar(
    pendientes: list[tuple[str, str, bool]],
    nuevos: list[tuple[str, str, bool]],
) -> list[tuple[str, str, bool]]:
    """Añade nuevos a la cola de pendientes. Si nuevos trae un cierre, los
    cierres viejos de pendientes que aún no se hablaron se descartan (así
    dos cierres leídos en ticks distintos no forman una retahíla). Avisos y
    permisos pendientes se conservan siempre, en su orden."""
    if any(kind == "cierre" for kind, _, _ in nuevos):
        pendientes = [p for p in pendientes if p[0] != "cierre"]
    return pendientes + nuevos
