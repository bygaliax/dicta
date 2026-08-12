"""Texto puro para la voz de salida: qué se lee y si acaba en pregunta.
El hook Stop entrega la respuesta completa; aquí se reduce a su prosa
hablable final: se saltan los párrafos-ruido (Sources, tablas, listas de
enlaces), se limpian markdown y URLs, y se acumulan párrafos desde el
final hasta el tope de caracteres. Si un único párrafo excede el tope,
se corta por frase conservando el final, que es donde Claude pregunta."""
import re

_FRASE = r"(?<=[.!?…])\s+"
_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_URL = re.compile(r"https?://\S+")
_ITEM_LISTA = re.compile(r"^[-*•]\s")
# Títulos que anuncian un bloque de fuentes/enlaces: no se leen en voz alta.
_TITULOS_RUIDO = {
    "sources", "source", "fuentes", "fuente",
    "referencias", "references", "enlaces", "links",
}


def _es_ruido(parrafo: str) -> bool:
    """Párrafos que no son prosa hablable: fuentes, tablas, listas de enlaces."""
    lineas = [linea.strip() for linea in parrafo.splitlines() if linea.strip()]
    if not lineas:
        return False  # lo vacío ya lo descarta _limpiar
    titulo = re.sub(r"[^\w ]", "", lineas[0].lower()).strip()
    if titulo in _TITULOS_RUIDO:
        return True
    if all(linea.startswith("|") for linea in lineas):
        return True  # tabla markdown
    items_con_enlace = sum(
        1
        for linea in lineas
        if _ITEM_LISTA.match(linea) and (_URL.search(linea) or _MD_LINK.search(linea))
    )
    # Lista de enlaces: al menos dos ítems-enlace y son la mayoría del bloque.
    # La prosa con un enlace inline no cae aquí (no empieza por guion).
    return items_con_enlace >= 2 and items_con_enlace * 2 >= len(lineas)


def _limpiar(text: str) -> str:
    """Markdown y URLs fuera: un TTS no debe leer asteriscos ni deletrear https."""
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = _MD_LINK.sub(r"\1", text)  # [texto](url) -> texto
    text = _URL.sub("", text)
    text = re.sub(r"^\s*[#>\-*]+\s*", "", text, flags=re.M)
    text = re.sub(r"[*_`]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def ultimo_parrafo(text: str, max_chars: int = 400) -> str:
    parrafos = re.split(r"\n\s*\n", text or "")
    limpios = [c for c in (_limpiar(p) for p in parrafos if not _es_ruido(p)) if c]
    if not limpios:
        return ""
    # Acumular párrafos completos desde el final; el primero entra siempre.
    out: list[str] = []
    total = 0
    for p in reversed(limpios):
        if out and total + len(p) + 1 > max_chars:
            break
        out.insert(0, p)
        total += len(p) + 1
    result = " ".join(out)
    if len(result) <= max_chars:
        return result
    # Un único párrafo mayor que el tope: cortar por frase conservando el final.
    frases = re.split(_FRASE, result)
    out = []
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
