"""Recuerda la última ventana/app en primer plano que no es el widget (ahí se
pega la transcripción) y la última terminal vista (a ella se ancla el widget).

Cross-platform: en Windows `last_hwnd`/`last_terminal_hwnd` son HWNDs; en macOS
son PIDs de la app frontal (AppKit no expone HWNDs). El injector y el docker
saben interpretar cada uno según la plataforma."""
import os
import sys

from dicta.docking import is_terminal_app, is_terminal_class


class FocusTracker:
    def __init__(self, own_hwnd: int) -> None:
        self.own_hwnd = own_hwnd          # HWND (win) — en mac no se usa
        self.own_pid = os.getpid()
        self.last_hwnd: int | None = None            # win: HWND | mac: PID
        self.last_terminal_hwnd: int | None = None   # win: HWND | mac: PID

    def poll(self) -> None:
        if sys.platform == "darwin":
            self._poll_mac()
        else:
            self._poll_win()

    # --- Windows ---
    def _poll_win(self) -> None:
        import win32gui
        hwnd = win32gui.GetForegroundWindow()
        if hwnd and hwnd != self.own_hwnd:
            self.last_hwnd = hwnd
            try:
                if is_terminal_class(win32gui.GetClassName(hwnd)):
                    self.last_terminal_hwnd = hwnd
            except Exception:
                pass  # la ventana pudo cerrarse entre medias

    # --- macOS ---
    def _poll_mac(self) -> None:
        try:
            from AppKit import NSWorkspace
            app = NSWorkspace.sharedWorkspace().frontmostApplication()
        except Exception:
            return
        if app is None:
            return
        pid = int(app.processIdentifier())
        if pid == self.own_pid:
            return  # nuestro propio widget Qt: ignorar
        self.last_hwnd = pid
        bundle = app.bundleIdentifier() or ""
        if is_terminal_app(bundle):
            self.last_terminal_hwnd = pid
