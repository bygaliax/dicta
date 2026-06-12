"""Pega la transcripción en la ventana destino vía clipboard, y lo restaura después.
Si no se puede pegar, el texto queda en el clipboard para paste manual.

Cross-platform: Windows usa win32 (clipboard + foreground window + keybd_event);
macOS usa pbcopy/pbpaste para el clipboard, AppKit para reactivar la app destino
(por PID) y pynput para el atajo de pegado (Cmd+V) — requiere permiso de
Accesibilidad. El `target` es un HWND en Windows y un PID en macOS."""
import subprocess
import sys
import time


# ───────────────────────── Windows ──────────────────────────
def _inject_win(text, target_hwnd, paste_shortcut, send_enter) -> bool:
    import win32api
    import win32clipboard
    import win32con
    import win32gui

    vk = {"ctrl": win32con.VK_CONTROL, "shift": win32con.VK_SHIFT,
          "alt": win32con.VK_MENU, "cmd": win32con.VK_LWIN, "v": ord("V")}

    def get_clip():
        win32clipboard.OpenClipboard()
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            return None
        finally:
            win32clipboard.CloseClipboard()

    def set_clip(t):
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, t)
        finally:
            win32clipboard.CloseClipboard()

    def shortcut(combo):
        keys = [vk[k.strip()] for k in combo.lower().split("+")]
        for k in keys:
            win32api.keybd_event(k, 0, 0, 0)
        for k in reversed(keys):
            win32api.keybd_event(k, 0, win32con.KEYEVENTF_KEYUP, 0)

    previous = get_clip()
    set_clip(text)
    if not target_hwnd or not win32gui.IsWindow(target_hwnd):
        return False
    win32gui.SetForegroundWindow(target_hwnd)
    time.sleep(0.1)
    shortcut(paste_shortcut)
    time.sleep(0.3)
    if send_enter:
        win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)
        win32api.keybd_event(win32con.VK_RETURN, 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(0.08)
    if previous is not None:
        try:
            set_clip(previous)
        except Exception:
            pass
    return True


# ───────────────────────── macOS ──────────────────────────
def _mac_get_clip():
    try:
        return subprocess.run(["pbpaste"], capture_output=True, text=True).stdout
    except Exception:
        return None


def _mac_set_clip(text):
    subprocess.run(["pbcopy"], input=text, text=True)


def _mac_activate_pid(pid):
    """Trae al frente la app destino (la terminal) por su PID antes de pegar."""
    try:
        from AppKit import NSRunningApplication
        app = NSRunningApplication.runningApplicationWithProcessIdentifier_(int(pid))
        if app is not None:
            app.activateWithOptions_(1 << 1)  # NSApplicationActivateIgnoringOtherApps
            return True
    except Exception:
        pass
    return False


def _mac_paste(send_enter):
    from pynput.keyboard import Controller, Key
    kb = Controller()
    with kb.pressed(Key.cmd):
        kb.press("v")
        kb.release("v")
    if send_enter:
        time.sleep(0.05)
        kb.press(Key.enter)
        kb.release(Key.enter)


def _inject_mac(text, target_pid, send_enter) -> bool:
    previous = _mac_get_clip()
    _mac_set_clip(text)
    if target_pid:
        _mac_activate_pid(target_pid)
        time.sleep(0.12)  # dar tiempo al cambio de foco
    _mac_paste(send_enter)
    time.sleep(0.25)
    if previous is not None:
        try:
            _mac_set_clip(previous)
        except Exception:
            pass
    return True


# ───────────────────────── API pública ──────────────────────────
def inject(
    text: str,
    target: int | None,
    paste_shortcut: str = "ctrl+v",
    send_enter: bool = False,
) -> bool:
    """Devuelve False si no pudo pegar (si fue posible, el texto queda en el clipboard).

    Nunca lanza: un fallo de clipboard/foco no debe tumbar el slot de Qt que llama.
    Con send_enter=True manda Enter tras pegar (envío directo, solo manos libres)."""
    try:
        if sys.platform == "win32":
            return _inject_win(text, target, paste_shortcut, send_enter)
        if sys.platform == "darwin":
            return _inject_mac(text, target, send_enter)
        # Otros: dejar el texto en el clipboard (best-effort) y avisar.
        subprocess.run(["xclip", "-selection", "clipboard"], input=text, text=True)
        return False
    except Exception as exc:
        print(f"No se pudo inyectar el texto: {exc}", file=sys.stderr)
        return False
