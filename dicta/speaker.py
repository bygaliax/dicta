"""Voz de salida. Speaker orquesta (hilo, stop, callbacks) con un motor
inyectable; crear_speaker construye el real (Kokoro ONNX, voz española)
y es el único sitio que importa kokoro_onnx. Si el modelo no está, se
descarga la primera vez (~310 MB) como los de Whisper y Vosk."""
import sys
import threading
import urllib.request
from pathlib import Path

import numpy as np

_BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
MODEL_URL = f"{_BASE}/kokoro-v1.0.onnx"
VOICES_URL = f"{_BASE}/voices-v1.0.bin"
BLOCK = 1024


def ensure_model(models_dir: Path) -> tuple[Path, Path]:
    """Devuelve (modelo, voces), descargándolos la primera vez (~310 MB)."""
    kdir = models_dir / "kokoro"
    kdir.mkdir(parents=True, exist_ok=True)
    rutas = []
    for url in (MODEL_URL, VOICES_URL):
        destino = kdir / url.rsplit("/", 1)[1]
        if not destino.exists():
            print(f"Descargando {destino.name}…")
            parcial = destino.with_suffix(destino.suffix + ".part")
            urllib.request.urlretrieve(url, parcial)
            parcial.rename(destino)
        rutas.append(destino)
    return rutas[0], rutas[1]


def _play(samples: np.ndarray, sr: int, stop: threading.Event, on_level) -> None:
    """Reproduce por bloques para poder cortar y publicar el nivel (RMS)."""
    import sounddevice as sd  # import perezoso

    with sd.OutputStream(samplerate=sr, channels=1, dtype="float32") as out:
        for i in range(0, len(samples), BLOCK):
            if stop.is_set():
                return
            chunk = np.ascontiguousarray(samples[i : i + BLOCK], dtype=np.float32)
            out.write(chunk)
            on_level(float(np.sqrt(np.mean(chunk**2))))


class Speaker:
    """speak() sintetiza y reproduce en un hilo; stop() corta. on_done se
    dispara SIEMPRE (fin normal, corte o error): la máquina de estados
    depende de ello para salir de SPEAKING."""

    def __init__(self, synth, player, on_level, on_done) -> None:
        self._synth = synth
        self._player = player
        self._on_level = on_level
        self._on_done = on_done
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def speak(self, text: str) -> bool:
        if self._thread is not None and self._thread.is_alive():
            return False
        self._stop.clear()

        def work() -> None:
            try:
                samples, sr = self._synth(text)
                if not self._stop.is_set():
                    self._player(samples, sr, self._stop, self._on_level)
            except Exception as exc:
                print(f"Error de voz: {exc}", file=sys.stderr)
            finally:
                self._on_done()

        self._thread = threading.Thread(target=work, daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop.set()


def crear_speaker(cfg, models_dir: Path, on_level, on_done) -> Speaker:
    """Construye el Speaker real con Kokoro ONNX (única función que lo importa)."""
    from kokoro_onnx import Kokoro  # import perezoso

    model, voices = ensure_model(models_dir)
    kokoro = Kokoro(str(model), str(voices))

    def synth(text: str):
        return kokoro.create(
            text, voice=cfg.voz_nombre, speed=cfg.voz_velocidad, lang="es"
        )

    return Speaker(synth, _play, on_level, on_done)
