"""Detector del wake word con Vosk en modo gramática: solo reconoce la
palabra configurada, el resto cae en [unk]. Se suscribe al AudioBus; el
trabajo pesado va en un hilo propio (el hilo de audio solo encola)."""
import json
import queue
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

import numpy as np

MODEL_NAME = "vosk-model-small-es-0.42"
MODEL_URL = f"https://alphacephei.com/vosk/models/{MODEL_NAME}.zip"
SAMPLE_RATE = 16000
DEBOUNCE_S = 1.0


def ensure_model(models_dir: Path) -> Path:
    """Devuelve la carpeta del modelo, descargándolo la primera vez (~39 MB)."""
    target = models_dir / MODEL_NAME
    if target.is_dir():
        return target
    models_dir.mkdir(parents=True, exist_ok=True)
    zip_path = models_dir / f"{MODEL_NAME}.zip"
    print(f"Descargando modelo de wake word ({MODEL_NAME}, ~39 MB)…")
    urllib.request.urlretrieve(MODEL_URL, zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(models_dir)
    zip_path.unlink()
    if not target.is_dir():
        raise RuntimeError(f"El zip no contenía {MODEL_NAME}")
    print("Modelo de wake word listo.")
    return target


def heard_word(result_json: str, word: str) -> bool:
    """True si el JSON de Vosk (parcial o final) contiene la palabra."""
    try:
        data = json.loads(result_json)
    except json.JSONDecodeError:
        return False
    text = data.get("partial") or data.get("text") or ""
    return word in text.split()


class WakeWordDetector:
    """feed() encola audio; un hilo lo pasa por Vosk y llama on_detect()
    (¡desde ese hilo!) al oír la palabra, con debounce de 1 s."""

    def __init__(
        self,
        model_dir: Path,
        word: str,
        on_detect,
        now=time.monotonic,
        recognizer=None,
    ) -> None:
        if recognizer is None:
            from vosk import KaldiRecognizer, Model, SetLogLevel  # import perezoso

            SetLogLevel(-1)
            recognizer = KaldiRecognizer(
                Model(str(model_dir)), SAMPLE_RATE, json.dumps([word, "[unk]"])
            )
        self.word = word
        self.on_detect = on_detect
        self._now = now
        self._recognizer = recognizer
        self._armed = False
        self._last_fire = -1e9
        self._queue: queue.Queue = queue.Queue(maxsize=64)
        threading.Thread(target=self._work, daemon=True).start()

    def set_armed(self, armed: bool) -> None:
        self._armed = armed

    def feed(self, chunk: np.ndarray) -> None:
        if not self._armed:
            return
        try:
            self._queue.put_nowait(chunk)
        except queue.Full:
            pass  # mejor perder audio que bloquear el hilo de audio

    def _work(self) -> None:
        while True:
            chunk = self._queue.get()
            if self._armed:
                self._process(chunk)

    def _process(self, chunk: np.ndarray) -> None:
        pcm = (np.clip(chunk, -1, 1) * 32767).astype("int16").tobytes()
        if self._recognizer.AcceptWaveform(pcm):
            result = self._recognizer.Result()
        else:
            result = self._recognizer.PartialResult()
        if heard_word(result, self.word) and self._now() - self._last_fire >= DEBOUNCE_S:
            self._last_fire = self._now()
            self._recognizer.Reset()
            self.on_detect()
