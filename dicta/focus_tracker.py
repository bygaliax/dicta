"""Recuerda la última ventana en primer plano que no es el widget (ahí se pega
la transcripción) y la última terminal vista (a ella se ancla el widget)."""
import win32gui

from dicta.docking import is_terminal_class


class FocusTracker:
    def __init__(self, own_hwnd: int) -> None:
        self.own_hwnd = own_hwnd
        self.last_hwnd: int | None = None
        self.last_terminal_hwnd: int | None = None

    def poll(self) -> None:
        hwnd = win32gui.GetForegroundWindow()
        if hwnd and hwnd != self.own_hwnd:
            self.last_hwnd = hwnd
            try:
                if is_terminal_class(win32gui.GetClassName(hwnd)):
                    self.last_terminal_hwnd = hwnd
            except Exception:
                pass  # la ventana pudo cerrarse entre medias
