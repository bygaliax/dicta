"""Graba el dictado tomando chunks del AudioBus (16 kHz mono float32)."""
import numpy as np

from dicta.audio import AudioBus


class Recorder:
    def __init__(self, bus: AudioBus) -> None:
        self.bus = bus
        self._chunks: list[np.ndarray] = []
        self._active = False

    def start(self) -> None:
        """Puede lanzar si el micrófono falla (lo propaga el bus)."""
        self._chunks = []
        self._active = True
        try:
            self.bus.subscribe(self._on_chunk)
        except Exception:
            self._active = False
            raise

    def stop(self) -> np.ndarray:
        self._active = False
        self.bus.unsubscribe(self._on_chunk)
        chunks, self._chunks = self._chunks, []
        if not chunks:
            return np.zeros(0, dtype="float32")
        return np.concatenate(chunks)

    def discard(self) -> None:
        """Aborta sin devolver audio (timeout del manos libres)."""
        self._active = False
        self.bus.unsubscribe(self._on_chunk)
        self._chunks = []

    def _on_chunk(self, chunk: np.ndarray) -> None:
        if self._active:
            self._chunks.append(chunk)
