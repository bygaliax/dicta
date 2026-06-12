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
DEFAULT_CONF = 0.85
# Señuelos fonéticos: palabras reales cercanas a "claude". Si el decoder tiene
# adónde mandar lo parecido, deja de forzarlo a la wake word ([unk] sale caro).
DECOYS = ["claro", "clave", "aplaude", "aplauden", "cuando"]


def ensure_model(models_dir: Path) -> Path:
    """Devuelve la carpeta del modelo, descargándolo la primera vez (~39 MB)."""
    target = models_dir / MODEL_NAME
    if target.is_dir():
        return target
    models_dir.mkdir(parents=True, exist_ok=True)
    zip_path = models_dir / f"{MODEL_NAME}.zip"
    print(f"Descargando modelo de wake word ({MODEL_NAME}, ~39 MB)…")
    urllib.request.urlretrieve(MODEL_URL, zip_path)
    try:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(models_dir)
    finally:
        zip_path.unlink(missing_ok=True)  # ni exito ni fallo dejan el zip atras
    if not target.is_dir():
        raise RuntimeError(f"El zip no contenía {MODEL_NAME}")
    print("Modelo de wake word listo.")
    return target


def heard_word(result_json: str, word: str, min_conf: float) -> bool:
    """True si el resultado FINAL de Vosk contiene la palabra con conf >= min_conf.
    Usa el array 'result' (requiere SetWords(True)); sin él, respaldo por texto."""
    try:
        data = json.loads(result_json)
    except json.JSONDecodeError:
        return False
    words = data.get("result")
    if words:
        return any(
            w.get("word") == word and w.get("conf", 0.0) >= min_conf for w in words
        )
    return word in (data.get("text") or "").split()


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
        min_conf: float = DEFAULT_CONF,
    ) -> None:
        if recognizer is None:
            from vosk import KaldiRecognizer, Model, SetLogLevel  # import perezoso

            SetLogLevel(-1)
            grammar = [word, *(d for d in DECOYS if d != word), "[unk]"]
            recognizer = KaldiRecognizer(
                Model(str(model_dir)), SAMPLE_RATE, json.dumps(grammar)
            )
            recognizer.SetWords(True)  # conf por palabra en el resultado final
        self.word = word
        self.on_detect = on_detect
        self._now = now
        self._min_conf = min_conf
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
        if not self._recognizer.AcceptWaveform(pcm):
            return  # los parciales son hipótesis inestables: solo confirmamos finales
        result = self._recognizer.Result()
        if (
            heard_word(result, self.word, self._min_conf)
            and self._now() - self._last_fire >= DEBOUNCE_S
        ):
            self._last_fire = self._now()
            self._recognizer.Reset()
            self.on_detect()
