"""Feedback sonoro corto. En hilo aparte para no bloquear la UI."""
import threading
import winsound

_SEQS = {
    "start": [(880, 120)],
    "stop": [(440, 120)],
    "error": [(220, 150), (180, 200)],
}


def play(name: str, enabled: bool = True) -> None:
    if not enabled or name not in _SEQS:
        return

    def _run() -> None:
        for freq, ms in _SEQS[name]:
            winsound.Beep(freq, ms)

    threading.Thread(target=_run, daemon=True).start()
