"""Recuerda la última ventana en primer plano que no es el widget.
El click en el widget roba el foco; sin esto no sabríamos dónde pegar."""
import win32gui


class FocusTracker:
    def __init__(self, own_hwnd: int) -> None:
        self.own_hwnd = own_hwnd
        self.last_hwnd: int | None = None

    def poll(self) -> None:
        hwnd = win32gui.GetForegroundWindow()
        if hwnd and hwnd != self.own_hwnd:
            self.last_hwnd = hwnd
