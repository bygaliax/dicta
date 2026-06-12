"""Captura de micrófono a 16 kHz mono float32 (lo que espera Whisper)."""
import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000


class Recorder:
    def __init__(self) -> None:
        self._chunks: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None

    def start(self) -> None:
        self._chunks = []
        try:
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                callback=lambda indata, frames, t, status: self._chunks.append(indata.copy()),
            )
            self._stream.start()
        except Exception:
            if self._stream is not None:
                self._stream.close()
            self._stream = None
            raise

    def stop(self) -> np.ndarray:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        chunks, self._chunks = self._chunks, []
        if not chunks:
            return np.zeros(0, dtype="float32")
        return np.concatenate(chunks).flatten()
