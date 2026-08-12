"""Texto puro para la voz de salida: qué se lee y si acaba en pregunta.
El hook Stop entrega la respuesta completa; aquí se reduce a su último
párrafo hablable (sin bloques de código ni marcas de markdown) con un
tope de caracteres que corta por frase conservando el final, que es
donde Claude pregunta."""
import re

_FRASE = r"(?<=[.!?…])\s+"


def _limpiar(text: str) -> str:
    """Markdown fuera: un TTS no debe leer asteriscos ni fences."""
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"^\s*[#>\-*]+\s*", "", text, flags=re.M)
    text = re.sub(r"[*_`]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def ultimo_parrafo(text: str, max_chars: int = 400) -> str:
    parrafos = [p for p in re.split(r"\n\s*\n", text or "")]
    limpios = [c for c in (_limpiar(p) for p in parrafos) if c]
    if not limpios:
        return ""
    ultimo = limpios[-1]
    if len(ultimo) <= max_chars:
        return ultimo
    frases = re.split(_FRASE, ultimo)
    out: list[str] = []
    total = 0
    for f in reversed(frases):
        if out and total + len(f) + 1 > max_chars:
            break
        out.insert(0, f)
        total += len(f) + 1
    result = " ".join(out)
    return result[-max_chars:] if len(result) > max_chars else result


def es_pregunta(text: str) -> bool:
    """True si alguna de las dos últimas frases contiene interrogación."""
    frases = re.split(_FRASE, (text or "").strip())
    return any("?" in f or "¿" in f for f in frases[-2:])
