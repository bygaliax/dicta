"""Feedback sonoro corto. En hilo aparte para no bloquear la UI.

Windows usa winsound.Beep (tonos exactos). macOS no deja generar tonos
arbitrarios sin librerías extra, así que usa el beep del sistema (uno para
start/stop, dos para error). Otros: campana de terminal."""
import sys
import threading

_SEQS = {
    "start": [(880, 120)],
    "stop": [(440, 120)],
    "error": [(220, 150), (180, 200)],
}


def _play_win(name: str) -> None:
    import winsound
    for freq, ms in _SEQS[name]:
        winsound.Beep(freq, ms)


def _play_mac(name: str) -> None:
    import subprocess
    beeps = len(_SEQS[name])  # error = 2, resto = 1
    subprocess.run(["osascript", "-e", f"beep {beeps}"], check=False)


def play(name: str, enabled: bool = True) -> None:
    if not enabled or name not in _SEQS:
        return

    def _run() -> None:
        try:
            if sys.platform == "win32":
                _play_win(name)
            elif sys.platform == "darwin":
                _play_mac(name)
            else:
                print("\a", end="", flush=True)
        except Exception:
            pass  # el sonido nunca debe tumbar nada

    threading.Thread(target=_run, daemon=True).start()
