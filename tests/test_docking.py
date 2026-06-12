"""Tests de la lógica pura de anclaje (sin Qt ni ventanas reales)."""
from dicta.docking import (
    MARGIN_BOTTOM,
    MARGIN_RIGHT,
    Docker,
    dock_position,
    is_terminal_class,
)


def test_detecta_terminales():
    assert is_terminal_class("CASCADIA_HOSTING_WINDOW_CLASS")  # Windows Terminal
    assert is_terminal_class("ConsoleWindowClass")  # cmd/PowerShell clásicos
    assert is_terminal_class("mintty")  # Git Bash


def test_ignora_otras_ventanas():
    assert not is_terminal_class("Chrome_WidgetWin_1")
    assert not is_terminal_class("")


def test_dock_position_esquina_inferior_derecha():
    x, y = dock_position((100, 100, 1000, 800), (72, 72))
    assert x == 1000 - 72 - MARGIN_RIGHT
    assert y == 800 - 72 - MARGIN_BOTTOM


def test_dock_position_aplica_offset_del_usuario():
    base = dock_position((0, 0, 500, 500), (72, 72))
    movido = dock_position((0, 0, 500, 500), (72, 72), (-30, 10))
    assert movido == (base[0] - 30, base[1] + 10)


class _FakeWidget:
    def __init__(self):
        self.moves = []
        self.hidden = False

    def is_dragging(self):
        return False

    def move(self, x, y):
        self.moves.append((x, y))

    def hide(self):
        self.hidden = True

    def show(self):
        self.hidden = False

    def x(self):
        return 0

    def y(self):
        return 0

    def width(self):
        return 72

    def height(self):
        return 72

    def winId(self):
        return 7


class _FakeTracker:
    last_terminal_hwnd = None


def test_sin_terminal_no_mueve_ni_oculta():
    w = _FakeWidget()
    d = Docker(w, _FakeTracker())
    d.tick()
    assert w.moves == []
    assert not w.hidden
    assert not d.docked


def test_drag_en_curso_pausa_el_anclaje():
    w = _FakeWidget()
    w.is_dragging = lambda: True
    tracker = _FakeTracker()
    tracker.last_terminal_hwnd = 12345  # ni se consulta: tick sale antes
    d = Docker(w, tracker)
    d.tick()
    assert w.moves == []


def test_dock_coloca_el_widget_sobre_la_terminal(monkeypatch):
    import dicta.docking as docking

    placed = []
    monkeypatch.setattr(docking, "place_above", lambda w, t: placed.append((w, t)))
    monkeypatch.setattr(docking.win32gui, "IsWindow", lambda h: True)
    monkeypatch.setattr(docking.win32gui, "IsIconic", lambda h: False)
    monkeypatch.setattr(docking.win32gui, "GetWindowRect", lambda h: (0, 0, 800, 600))
    w = _FakeWidget()
    tracker = _FakeTracker()
    tracker.last_terminal_hwnd = 99
    d = Docker(w, tracker)
    d.tick()
    assert placed == [(7, 99)]
