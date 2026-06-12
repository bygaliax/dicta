"""Orquestador: une widget, estados, grabadora, transcriptor e inyector."""
import json
import sys
import threading
from pathlib import Path

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication

from dicta import injector, singleton, sounds
from dicta.config import APP_DIR, Config, ensure_config, load_config
from dicta.focus_tracker import FocusTracker
from dicta.recorder import Recorder
from dicta.state import State, StateMachine
from dicta.widget import DictaWidget

STATE_FILE = APP_DIR / "state.json"
EXAMPLE_CONFIG = Path(__file__).parent.parent / "config.example.toml"


class Bridge(QObject):
    """Señales para cruzar de hilos de trabajo al hilo de Qt (thread-safe)."""

    model_ready = pyqtSignal()
    model_failed = pyqtSignal()
    transcription_done = pyqtSignal(str)
    transcription_failed = pyqtSignal()
    injection_finished = pyqtSignal(bool)
    hotkey_pressed = pyqtSignal()


def load_position() -> tuple[int, int] | None:
    try:
        d = json.loads(STATE_FILE.read_text())
        return int(d["x"]), int(d["y"])
    except Exception:
        return None


def save_position(x: int, y: int) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"x": x, "y": y}))


def main() -> int:
    if singleton.already_running():
        print("dicta ya está corriendo.")
        return 0
    singleton.write_pid()
    if EXAMPLE_CONFIG.exists():
        ensure_config(EXAMPLE_CONFIG)
    cfg: Config = load_config()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    sm = StateMachine()
    widget = DictaWidget()
    recorder = Recorder()
    bridge = Bridge()
    holder: dict = {}  # {"t": Transcriber} cuando cargue

    # Posición: persistida, o esquina inferior derecha por defecto
    pos = load_position()
    if pos:
        widget.move(*pos)
    else:
        geo = app.primaryScreen().availableGeometry()
        widget.move(geo.right() - 80, geo.bottom() - 80)
    widget.show()

    tracker = FocusTracker(int(widget.winId()))
    poll_timer = QTimer()
    poll_timer.timeout.connect(tracker.poll)
    poll_timer.start(500)

    # --- cableado de estados y UI ---
    sm.on_change.append(widget.set_state)
    widget.clicked.connect(sm.click)
    widget.quit_requested.connect(app.quit)
    bridge.model_ready.connect(sm.model_ready)
    bridge.model_failed.connect(sm.fail)
    bridge.hotkey_pressed.connect(sm.click)

    # --- grabación ---
    def start_recording() -> None:
        sounds.play("start", cfg.sonidos)
        try:
            recorder.start()
        except Exception as exc:
            print(f"Error de micrófono: {exc}", file=sys.stderr)
            sounds.play("error", cfg.sonidos)
            sm.fail()

    def stop_and_transcribe() -> None:
        sounds.play("stop", cfg.sonidos)
        audio = recorder.stop()

        def work() -> None:
            try:
                text = holder["t"].transcribe(audio)
                bridge.transcription_done.emit(text)
            except Exception as exc:
                print(f"Error transcribiendo: {exc}", file=sys.stderr)
                bridge.transcription_failed.emit()

        threading.Thread(target=work, daemon=True).start()

    sm.on_start_listening.append(start_recording)
    sm.on_stop_listening.append(stop_and_transcribe)

    # --- resultado de la transcripción ---
    def on_done(text: str) -> None:
        if not text:
            sounds.play("error", cfg.sonidos)  # silencio/ruido: no pegar nada
            sm.transcription_done()
            return
        # inject duerme ~0.4s (foco + paste): fuera del hilo de Qt para no congelar la UI
        target = tracker.last_hwnd
        threading.Thread(
            target=lambda: bridge.injection_finished.emit(
                injector.inject(text, target, cfg.paste_shortcut)
            ),
            daemon=True,
        ).start()

    def on_injection_finished(ok: bool) -> None:
        if not ok:
            sounds.play("error", cfg.sonidos)  # quedó en el clipboard
            print("No se pudo pegar; la transcripción está en el clipboard.")
        sm.transcription_done()

    bridge.transcription_done.connect(on_done)
    bridge.injection_finished.connect(on_injection_finished)
    bridge.transcription_failed.connect(lambda: (sounds.play("error", cfg.sonidos), sm.fail()))

    # --- carga del modelo en background ---
    def load_model() -> None:
        try:
            from dicta.transcriber import Transcriber

            print(f"Cargando modelo {cfg.model}… (la primera vez descarga ~3 GB)")
            holder["t"] = Transcriber(cfg.model, cfg.language, cfg.vocabulario)
            print(f"Modelo listo en {holder['t'].device}.")
            bridge.model_ready.emit()
        except Exception as exc:
            print(f"No se pudo cargar el modelo: {exc}", file=sys.stderr)
            bridge.model_failed.emit()

    threading.Thread(target=load_model, daemon=True).start()

    # --- hotkey opcional ---
    if cfg.hotkey_enabled:
        import keyboard

        keyboard.add_hotkey(cfg.hotkey_combo, bridge.hotkey_pressed.emit)

    # --- auto-cierre cuando los hooks indican 0 sesiones de Claude Code ---
    exit_timer = QTimer()
    exit_timer.timeout.connect(
        lambda: app.quit() if singleton.should_exit(singleton.read_counter()) else None
    )
    exit_timer.start(2000)

    app.aboutToQuit.connect(lambda: save_position(widget.x(), widget.y()))
    return app.exec()
