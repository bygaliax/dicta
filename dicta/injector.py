"""Pega la transcripción en la ventana destino vía clipboard, y lo restaura después.
Si no se puede pegar, el texto queda en el clipboard para paste manual."""
import sys
import time

import win32api
import win32clipboard
import win32con
import win32gui

_VK = {
    "ctrl": win32con.VK_CONTROL,
    "shift": win32con.VK_SHIFT,
    "alt": win32con.VK_MENU,
    "v": ord("V"),
}


def _get_clipboard_text() -> str | None:
    win32clipboard.OpenClipboard()
    try:
        if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
            return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
        return None  # contenido no-texto (imagen, etc.): no lo restauramos
    finally:
        win32clipboard.CloseClipboard()


def _set_clipboard_text(text: str) -> None:
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
    finally:
        win32clipboard.CloseClipboard()


def _send_shortcut(combo: str) -> None:
    keys = [_VK[k.strip()] for k in combo.lower().split("+")]
    for k in keys:
        win32api.keybd_event(k, 0, 0, 0)
    for k in reversed(keys):
        win32api.keybd_event(k, 0, win32con.KEYEVENTF_KEYUP, 0)


def inject(text: str, target_hwnd: int | None, paste_shortcut: str = "ctrl+v") -> bool:
    """Devuelve False si no pudo pegar (si fue posible, el texto queda en el clipboard).

    Nunca lanza: el clipboard puede estar bloqueado por otra app (OpenClipboard
    falla con access denied) y eso no debe tumbar el slot de Qt que nos llama.
    """
    try:
        previous = _get_clipboard_text()
        _set_clipboard_text(text)
        if not target_hwnd or not win32gui.IsWindow(target_hwnd):
            return False
        win32gui.SetForegroundWindow(target_hwnd)
        time.sleep(0.1)  # dar tiempo al cambio de foco
        _send_shortcut(paste_shortcut)
        time.sleep(0.3)  # dar tiempo al paste antes de restaurar el clipboard
        if previous is not None:
            try:
                _set_clipboard_text(previous)
            except Exception:
                pass  # restaurar es best-effort; el paste ya ocurrió
        return True
    except Exception as exc:
        print(f"No se pudo inyectar el texto: {exc}", file=sys.stderr)
        return False
