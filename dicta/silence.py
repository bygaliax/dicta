"""Corte por silencio para sesiones manos libres. Acumula audio en ventanas
de ~0.5 s y pregunta a un VAD si hay voz. Tras `silence_s` seguidos sin voz
(habiendo oído voz antes) devuelve "silence"; si nunca llega voz en
`timeout_s`, devuelve "timeout". El VAD es inyectable para tests; el real
reutiliza el Silero que ya trae faster-whisper (sin dependencia nueva)."""
import numpy as np

SAMPLE_RATE = 16000
WINDOW_S = 0.5


def _vad_has_speech(window: np.ndarray) -> bool:
    from faster_whisper.vad import VadOptions, get_speech_timestamps  # import perezoso

    return bool(get_speech_timestamps(window, VadOptions()))


class SilenceDetector:
    def __init__(
        self,
        silence_s: float = 2.0,
        timeout_s: float = 10.0,
        has_speech=_vad_has_speech,
    ) -> None:
        self.silence_s = silence_s
        self.timeout_s = timeout_s
        self.has_speech = has_speech
        self.reset()

    def reset(self) -> None:
        self._buffer: list[np.ndarray] = []
        self._buffered = 0
        self._heard_speech = False
        self._silence = 0.0
        self._elapsed = 0.0
        self._fired = False

    def feed(self, chunk: np.ndarray) -> str | None:
        """Devuelve "silence", "timeout" o None. Tras disparar queda inerte."""
        if self._fired:
            return None
        self._buffer.append(chunk)
        self._buffered += len(chunk)
        if self._buffered < SAMPLE_RATE * WINDOW_S:
            return None
        window = np.concatenate(self._buffer)
        self._buffer = []
        self._buffered = 0
        seconds = len(window) / SAMPLE_RATE
        self._elapsed += seconds
        if self.has_speech(window):
            self._heard_speech = True
            self._silence = 0.0
        else:
            self._silence += seconds
        if self._heard_speech and self._silence >= self.silence_s:
            self._fired = True
            return "silence"
        if not self._heard_speech and self._elapsed >= self.timeout_s:
            self._fired = True
            return "timeout"
        return None
