"""Instancia única (mutex de Windows) + pidfile + contador de sesiones de los hooks."""
import os
import sys
from pathlib import Path

from dicta.config import APP_DIR

COUNTER_FILE = APP_DIR / "sessions.count"
PID_FILE = APP_DIR / "dicta.pid"

_mutex_handle = None  # mantener vivo el handle mientras el proceso exista


def read_counter(path: Path = COUNTER_FILE) -> int | None:
    """None = sin hooks (lanzado a mano): la app nunca debe auto-salir."""
    try:
        return int(path.read_text().strip())
    except (OSError, ValueError):
        return None


def should_exit(counter: int | None) -> bool:
    return counter is not None and counter <= 0


def write_pid(path: Path = PID_FILE) -> None:
    """El pidfile es solo para que el hook de arranque detecte la instancia; la unicidad real la da el mutex."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(os.getpid()))


def already_running(path: Path = PID_FILE) -> bool:
    global _mutex_handle
    if sys.platform == "win32":
        import win32api
        import win32event
        import winerror

        _mutex_handle = win32event.CreateMutex(None, False, "Global\\dicta_singleton")
        return win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS

    # POSIX (macOS/Linux): pidfile + comprobación de proceso vivo.
    try:
        pid = int(path.read_text().strip())
    except (OSError, ValueError):
        return False
    if pid == os.getpid():
        return False
    try:
        os.kill(pid, 0)  # señal 0 = solo comprueba existencia
        return True
    except OSError:
        return False  # pidfile huérfano (proceso muerto)
