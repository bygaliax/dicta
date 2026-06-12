"""Instancia única (mutex de Windows) + pidfile + contador de sesiones de los hooks."""
import os
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


def already_running() -> bool:
    global _mutex_handle
    import win32api
    import win32event
    import winerror

    # "Global\\": una sola instancia por máquina (cubre RDP/runas); suficiente para desktop single-user.
    _mutex_handle = win32event.CreateMutex(None, False, "Global\\dicta_singleton")
    return win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS
