"""Orquestador: une widget, estados, bus de audio, wake word, grabadora,
transcriptor e inyector."""
import json
import sys
import threading
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication

from dicta import injector, singleton, sounds
from dicta.audio import AudioBus
from dicta.config import APP_DIR, Config, ensure_config, load_config
from dicta.docking import Docker
from dicta.focus_tracker import FocusTracker
from dicta.recorder import Recorder
from dicta.silence import SilenceDetector
from dicta.speak_queue import drenar_cola, preparar
from dicta.state import State, StateMachine
from dicta.widget import DictaWidget

STATE_FILE = APP_DIR / "state.json"
MODELS_DIR = APP_DIR / "models"
SPEAK_DIR = APP_DIR / "speak"
EXAMPLE_CONFIG = Path(__file__).parent.parent / "config.example.toml"


class Bridge(QObject):
    """Señales para cruzar de hilos de trabajo al hilo de Qt (thread-safe)."""

    model_ready = pyqtSignal()
    model_failed = pyqtSignal()
    transcription_done = pyqtSignal(str)
    transcription_failed = pyqtSignal()
    injection_finished = pyqtSignal(bool)
    hotkey_pressed = pyqtSignal()
    wake_detected = pyqtSignal()
    wake_ready = pyqtSignal()
    wake_failed = pyqtSignal()
    silence_event = pyqtSignal(str)  # "silence" | "timeout"
    mic_level = pyqtSignal(float)
    speak_done = pyqtSignal()
    speak_level = pyqtSignal(float)
    voz_failed = pyqtSignal()


def load_ui_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {}


def save_ui_state(widget, docker: Docker) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(
            {
                "x": widget.x(),
                "y": widget.y(),
                "dx": docker.offset[0],
                "dy": docker.offset[1],
            }
        )
    )


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
    sm = StateMachine(handsfree_enabled=cfg.manos_libres_activado)
    widget = DictaWidget()
    bus = AudioBus()
    recorder = Recorder(bus)
    bridge = Bridge()
    holder: dict = {}           # {"t": Transcriber} cuando cargue
    detector_holder: dict = {}  # {"d": WakeWordDetector} cuando cargue
    silence_holder: dict = {}   # {"s": SilenceDetector, "cb": callback} por sesión

    # Posición inicial: persistida, o esquina inferior derecha por defecto.
    ui_state = load_ui_state()
    if "x" in ui_state and "y" in ui_state:
        widget.move(int(ui_state["x"]), int(ui_state["y"]))
    else:
        geo = app.primaryScreen().availableGeometry()
        widget.move(geo.right() - widget.width() - 16, geo.bottom() - widget.height() - 16)
    widget.show()

    tracker = FocusTracker(int(widget.winId()))
    poll_timer = QTimer()
    poll_timer.timeout.connect(tracker.poll)
    poll_timer.start(500)

    docker = Docker(
        widget, tracker, (int(ui_state.get("dx", 0)), int(ui_state.get("dy", 0)))
    )
    dock_timer = QTimer()
    dock_timer.timeout.connect(docker.tick)
    dock_timer.start(80)
    widget.drag_finished.connect(docker.recompute_offset)

    # --- cableado de estados y UI ---
    sm.on_change.append(widget.set_state)
    widget.clicked.connect(sm.click)
    widget.quit_requested.connect(app.quit)
    bridge.model_ready.connect(sm.model_ready)
    bridge.model_failed.connect(sm.fail)
    bridge.hotkey_pressed.connect(sm.click)
    bridge.wake_detected.connect(sm.wake_detected)
    bridge.mic_level.connect(widget.set_level)

    # --- nivel del micrófono -> barras (solo mientras se escucha) ---
    level_counter = {"n": 0}

    def on_chunk_level(chunk: np.ndarray) -> None:
        level_counter["n"] += 1
        if level_counter["n"] % 3 == 0:  # ~30 fps con chunks de ~10 ms
            bridge.mic_level.emit(float(np.sqrt(np.mean(chunk**2))))

    # --- grabación ---
    def start_recording() -> None:
        if "t" not in holder:
            print("El modelo no está cargado; no se puede dictar.", file=sys.stderr)
            sounds.play("error", cfg.sonidos)
            sm.fail()
            return
        sounds.play("start", cfg.sonidos)
        try:
            recorder.start()
            bus.subscribe(on_chunk_level)
        except Exception as exc:
            print(f"Error de micrófono: {exc}", file=sys.stderr)
            sounds.play("error", cfg.sonidos)
            sm.fail()
            return
        if sm.session_handsfree:
            det = SilenceDetector(cfg.silencio_segundos)
            silence_holder["s"] = det

            def feed_silence(chunk: np.ndarray, _det=det) -> None:
                event = _det.feed(chunk)
                if event:
                    bridge.silence_event.emit(event)

            silence_holder["cb"] = feed_silence
            bus.subscribe(feed_silence)

    def cleanup_listening() -> None:
        bus.unsubscribe(on_chunk_level)
        cb = silence_holder.pop("cb", None)
        if cb is not None:
            bus.unsubscribe(cb)
        silence_holder.pop("s", None)

    def stop_and_transcribe() -> None:
        sounds.play("stop", cfg.sonidos)
        cleanup_listening()
        audio_data = recorder.stop()

        def work() -> None:
            try:
                text = holder["t"].transcribe(audio_data)
                bridge.transcription_done.emit(text)
            except Exception as exc:
                print(f"Error transcribiendo: {exc}", file=sys.stderr)
                bridge.transcription_failed.emit()

        threading.Thread(target=work, daemon=True).start()

    def cancel_listening() -> None:
        cleanup_listening()
        recorder.discard()
        sounds.play("error", cfg.sonidos)

    sm.on_start_listening.append(start_recording)
    sm.on_stop_listening.append(stop_and_transcribe)
    sm.on_cancel_listening.append(cancel_listening)

    def on_silence_event(event: str) -> None:
        if event == "silence":
            sm.silence_detected()
        else:  # "timeout": nunca hubo voz
            sm.cancel()

    bridge.silence_event.connect(on_silence_event)

    # --- resultado de la transcripción ---
    def on_done(text: str) -> None:
        if not text:
            sounds.play("error", cfg.sonidos)  # silencio/ruido: no pegar nada
            sm.transcription_done()
            return
        # En manos libres el destino es SIEMPRE la terminal (un Enter automático
        # en otra app sería peligroso); en manual, la última ventana activa.
        handsfree = sm.session_handsfree
        target = tracker.last_terminal_hwnd if handsfree else tracker.last_hwnd
        send_enter = handsfree and cfg.auto_enviar
        threading.Thread(
            target=lambda: bridge.injection_finished.emit(
                injector.inject(text, target, cfg.paste_shortcut, send_enter)
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
    bridge.transcription_failed.connect(
        lambda: (sounds.play("error", cfg.sonidos), sm.fail())
    )

    # --- wake word ---
    def load_wakeword() -> None:
        try:
            from dicta.wakeword import WakeWordDetector, ensure_model

            model_dir = ensure_model(MODELS_DIR)
            detector_holder["d"] = WakeWordDetector(
                model_dir, cfg.wake_word, bridge.wake_detected.emit,
                min_conf=cfg.wake_confianza,
            )
            detector_holder.pop("loading", None)
            bridge.wake_ready.emit()
        except Exception as exc:
            print(f"Wake word no disponible: {exc}", file=sys.stderr)
            detector_holder.pop("loading", None)
            bridge.wake_failed.emit()

    def launch_wakeword_load() -> None:
        """Lanza la carga una sola vez aunque el toggle llegue varias veces."""
        if "d" in detector_holder or "loading" in detector_holder:
            return
        detector_holder["loading"] = True
        threading.Thread(target=load_wakeword, daemon=True).start()

    def sync_detector(state: State) -> None:
        """El detector solo procesa en ARMED; suscrito salvo en reposo apagado."""
        det = detector_holder.get("d")
        if det is None:
            return
        det.set_armed(state is State.ARMED)
        if state is State.ARMED:
            try:
                bus.subscribe(det.feed)
            except Exception as exc:
                print(f"Error de micrófono: {exc}", file=sys.stderr)
                sm.fail()
        elif state in (State.IDLE, State.ERROR):
            bus.unsubscribe(det.feed)

    sm.on_change.append(sync_detector)
    bridge.wake_ready.connect(lambda: sync_detector(sm.state))

    def on_wake_failed() -> None:
        if sm.handsfree_enabled:
            sm.toggle_handsfree()  # manos libres OFF; el flujo manual sigue
        widget.set_handsfree(False)

    bridge.wake_failed.connect(on_wake_failed)

    def on_handsfree_toggled(enabled: bool) -> None:
        if enabled:
            launch_wakeword_load()
        if enabled != sm.handsfree_enabled:
            sm.toggle_handsfree()
        widget.set_handsfree(enabled)

    widget.handsfree_toggled.connect(on_handsfree_toggled)
    widget.set_handsfree(cfg.manos_libres_activado)
    if cfg.manos_libres_activado:
        launch_wakeword_load()

    # --- voz de salida (v3): cola de los hooks -> Kokoro ---
    voz_holder: dict = {}                       # {"s": Speaker} cuando cargue
    pendientes: list[tuple[str, bool]] = []     # (texto, abre_mic)
    voz_on = {"v": cfg.voz_activada}

    def load_voz() -> None:
        try:
            from dicta.speaker import crear_speaker

            voz_holder["s"] = crear_speaker(
                cfg, MODELS_DIR, bridge.speak_level.emit,
                bridge.speak_done.emit,
            )
            print("Voz lista.")
        except Exception as exc:
            print(f"Voz no disponible: {exc}", file=sys.stderr)
            bridge.voz_failed.emit()

    if cfg.voz_activada:
        threading.Thread(target=load_voz, daemon=True).start()

    def on_voz_failed() -> None:
        voz_on["v"] = False
        widget.set_voice(False)

    bridge.voz_failed.connect(on_voz_failed)

    def intentar_hablar() -> None:
        if not pendientes:
            return
        if not voz_on["v"]:
            pendientes.clear()  # muteado o sin motor: la cola no debe crecer
            return
        if "s" not in voz_holder:
            return  # aún cargando; el coalescing mantiene la cola corta
        texto, abre_mic = pendientes[0]
        if sm.speak_request(abre_mic):
            pendientes.pop(0)
            voz_holder["s"].speak(texto)

    def revisar_cola() -> None:
        items = drenar_cola(SPEAK_DIR)
        if items:
            pendientes.extend(
                preparar(
                    items, cfg.voz_max_caracteres, cfg.leer_avisos,
                    cfg.leer_cierres, cfg.escuchar_tras_pregunta,
                )
            )
        intentar_hablar()

    speak_timer = QTimer()
    speak_timer.timeout.connect(revisar_cola)
    speak_timer.start(500)

    bridge.speak_done.connect(sm.speak_done)
    bridge.speak_level.connect(widget.set_level)
    sm.on_stop_speaking.append(
        lambda: voz_holder["s"].stop() if "s" in voz_holder else None
    )

    def reintentar_pendientes(state: State) -> None:
        if state in (State.IDLE, State.ARMED) and pendientes:
            QTimer.singleShot(0, intentar_hablar)

    sm.on_change.append(reintentar_pendientes)

    def on_voice_toggled(enabled: bool) -> None:
        voz_on["v"] = enabled
        if not enabled and "s" in voz_holder:
            voz_holder["s"].stop()  # si estaba hablando, silencio inmediato

    widget.voice_toggled.connect(on_voice_toggled)
    widget.set_voice(cfg.voz_activada)

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

    app.aboutToQuit.connect(lambda: save_ui_state(widget, docker))
    return app.exec()
