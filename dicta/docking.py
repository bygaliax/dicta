"""Ancla el widget a la ventana de la terminal (Windows): lo pega a la esquina
inferior derecha y la sigue al moverse/redimensionar.

En macOS (v1) el anclaje a la ventana de la terminal está pendiente — requiere
Quartz/CGWindowList. Por ahora el widget flota donde lo dejes (su posición se
recuerda entre sesiones). El resto del flujo (dictado → pegar) funciona igual."""
import sys

# Clases de ventana de las terminales habituales en Windows.
TERMINAL_CLASSES = {
    "CASCADIA_HOSTING_WINDOW_CLASS",  # Windows Terminal
    "ConsoleWindowClass",             # cmd / PowerShell clásicos (conhost)
    "mintty",                         # Git Bash
}

# Bundle IDs de las terminales habituales en macOS.
TERMINAL_BUNDLES = {
    "com.apple.Terminal",
    "com.googlecode.iterm2",
    "dev.warp.Warp-Stable",
    "net.kovidgoyal.kitty",
    "io.alacritty",
    "com.github.wez.wezterm",
    "co.zeit.hyper",
    "com.microsoft.VSCode",          # terminal integrada
    "com.todesktop.230313mzl4w4u92", # Cursor
}

MARGIN_RIGHT = 14
MARGIN_BOTTOM = 76  # por encima de la caja de input de Claude Code


def is_terminal_class(class_name: str) -> bool:
    return class_name in TERMINAL_CLASSES


def is_terminal_app(bundle_id: str) -> bool:
    return bundle_id in TERMINAL_BUNDLES


def dock_position(rect, size, offset=(0, 0)):
    """Posición pegada a la esquina inferior derecha de la terminal (Windows)."""
    _, _, right, bottom = rect
    w, h = size
    return right - w - MARGIN_RIGHT + offset[0], bottom - h - MARGIN_BOTTOM + offset[1]


def place_above(widget_hwnd: int, terminal_hwnd: int) -> None:
    import win32con
    import win32gui
    prev = win32gui.GetWindow(terminal_hwnd, win32con.GW_HWNDPREV)
    if prev == widget_hwnd:
        return
    flags = win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE
    win32gui.SetWindowPos(widget_hwnd, prev, 0, 0, 0, 0, flags)


class Docker:
    """Llamar a tick() periódicamente (QTimer). El widget solo necesita
    move/hide/show/x/y/size. En macOS el anclaje es no-op (flota)."""

    def __init__(self, widget, tracker, offset=(0, 0)) -> None:
        self.widget = widget
        self.tracker = tracker
        self.offset = offset
        self.docked = False
        self._hidden = False
        self._mac = sys.platform == "darwin"

    def tick(self) -> None:
        if self._mac or sys.platform not in ("win32",):
            self._show()   # v1 no-Windows: el widget flota donde lo dejes
            return
        import win32gui
        if self.widget.is_dragging():
            return
        hwnd = self.tracker.last_terminal_hwnd
        if not hwnd or not win32gui.IsWindow(hwnd):
            self.docked = False
            self._show()
            return
        if win32gui.IsIconic(hwnd):
            self._hide()
            return
        self._show()
        x, y = dock_position(win32gui.GetWindowRect(hwnd), self._size(), self.offset)
        self.docked = True
        if (x, y) != (self.widget.x(), self.widget.y()):
            self.widget.move(x, y)
        try:
            place_above(int(self.widget.winId()), hwnd)
        except Exception:
            pass

    def recompute_offset(self) -> None:
        if self._mac or sys.platform != "win32":
            return  # flota: la posición la recuerda save_ui_state (x, y)
        import win32gui
        hwnd = self.tracker.last_terminal_hwnd
        if not (self.docked and hwnd and win32gui.IsWindow(hwnd)):
            return
        ax, ay = dock_position(win32gui.GetWindowRect(hwnd), self._size())
        self.offset = (self.widget.x() - ax, self.widget.y() - ay)

    def _size(self):
        return self.widget.width(), self.widget.height()

    def _hide(self) -> None:
        if not self._hidden:
            self.widget.hide()
            self._hidden = True

    def _show(self) -> None:
        if self._hidden:
            self.widget.show()
            self._hidden = False
