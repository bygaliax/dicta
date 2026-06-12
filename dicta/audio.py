"""Bus de audio compartido: un solo InputStream de 16 kHz mono float32 para
wake word, grabadora y VAD a la vez (sin pelearse por el micrófono).
Se abre con el primer suscriptor y se cierra con el último. Los callbacks
reciben cada chunk como np.ndarray 1-D float32 — ¡desde el hilo de audio!
(nada pesado ahí: encolar o acumular y volver)."""
import threading

import sounddevice as sd

SAMPLE_RATE = 16000


class AudioBus:
    def __init__(self) -> None:
        self._subs: list = []
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()

    def subscribe(self, callback) -> None:
        """Puede lanzar si el micrófono falla al abrir el stream."""
        with self._lock:
            if callback in self._subs:
                return
            self._subs.append(callback)
            if self._stream is None:
                try:
                    self._open()
                except Exception:
                    self._subs.remove(callback)
                    raise

    def unsubscribe(self, callback) -> None:
        with self._lock:
            if callback in self._subs:
                self._subs.remove(callback)
            if not self._subs and self._stream is not None:
                stream, self._stream = self._stream, None
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass  # dispositivo desconectado: el stream ya está muerto

    def _open(self) -> None:
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            callback=self._on_audio,
        )
        try:
            self._stream.start()
        except Exception:
            self._stream.close()
            self._stream = None
            raise

    def _on_audio(self, indata, frames, time_info, status) -> None:
        chunk = indata[:, 0].copy()
        for cb in list(self._subs):
            try:
                cb(chunk)
            except Exception:
                pass  # un suscriptor roto no debe tumbar el stream
