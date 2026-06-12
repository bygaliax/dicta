"""Ancla el widget a la ventana de la terminal: lo pega a la esquina inferior
derecha y la sigue cuando se mueve o cambia de tamaño. Si la terminal se
minimiza, el widget se oculta; si no hay terminal a la vista, queda flotando."""
import win32con
import win32gui

# Clases de ventana de las terminales habituales en Windows.
TERMINAL_CLASSES = {
    "CASCADIA_HOSTING_WINDOW_CLASS",  # Windows Terminal
    "ConsoleWindowClass",             # cmd / PowerShell clásicos (conhost)
    "mintty",                         # Git Bash
}

MARGIN_RIGHT = 14
MARGIN_BOTTOM = 76  # por encima de la caja de input de Claude Code


def is_terminal_class(class_name: str) -> bool:
    return class_name in TERMINAL_CLASSES


def place_above(widget_hwnd: int, terminal_hwnd: int) -> None:
    """Coloca el widget justo encima de la terminal en el z-order (sin topmost):
    si otra app tapa la terminal, tapa también el widget."""
    prev = win32gui.GetWindow(terminal_hwnd, win32con.GW_HWNDPREV)
    if prev == widget_hwnd:
        return
    flags = win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE
    win32gui.SetWindowPos(widget_hwnd, prev, 0, 0, 0, 0, flags)


def dock_position(
    rect: tuple[int, int, int, int],
    size: tuple[int, int],
    offset: tuple[int, int] = (0, 0),
) -> tuple[int, int]:
    """Posición pegada a la esquina inferior derecha de la terminal.
    `offset` es el ajuste manual del usuario (drag), relativo al ancla."""
    _, _, right, bottom = rect
    w, h = size
    return right - w - MARGIN_RIGHT + offset[0], bottom - h - MARGIN_BOTTOM + offset[1]


class Docker:
    """Llamar a tick() periódicamente (QTimer). Sin estado Qt propio para
    poder probarlo con dobles; el widget solo necesita move/hide/show/x/y/size."""

    def __init__(self, widget, tracker, offset: tuple[int, int] = (0, 0)) -> None:
        self.widget = widget
        self.tracker = tracker
        self.offset = offset
        self.docked = False
        self._hidden = False

    def tick(self) -> None:
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
            pass  # la terminal pudo cerrarse entre medias

    def recompute_offset(self) -> None:
        """Tras un drag del usuario: el nuevo offset es donde dejó el widget
        respecto al ancla, y se mantiene aunque la terminal se mueva."""
        hwnd = self.tracker.last_terminal_hwnd
        if not (self.docked and hwnd and win32gui.IsWindow(hwnd)):
            return
        ax, ay = dock_position(win32gui.GetWindowRect(hwnd), self._size())
        self.offset = (self.widget.x() - ax, self.widget.y() - ay)

    def _size(self) -> tuple[int, int]:
        return self.widget.width(), self.widget.height()

    def _hide(self) -> None:
        if not self._hidden:
            self.widget.hide()
            self._hidden = True

    def _show(self) -> None:
        if self._hidden:
            self.widget.show()
            self._hidden = False
