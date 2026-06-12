"""Whisper local vía faster-whisper. CUDA float16; fallback a CPU int8."""
import numpy as np


def build_initial_prompt(vocabulario: list[str]) -> str | None:
    if not vocabulario:
        return None
    return "Transcripción técnica. Vocabulario: " + ", ".join(vocabulario) + "."


class Transcriber:
    def __init__(self, model: str, language: str, vocabulario: list[str]) -> None:
        from faster_whisper import WhisperModel  # import perezoso: tarda y pesa

        self.language = language
        self.initial_prompt = build_initial_prompt(vocabulario)
        try:
            self.model = WhisperModel(model, device="cuda", compute_type="float16")
            self.device = "cuda"
        except Exception:
            self.model = WhisperModel(model, device="cpu", compute_type="int8")
            self.device = "cpu"

    def transcribe(self, audio: np.ndarray) -> str:
        segments, _info = self.model.transcribe(
            audio,
            language=self.language,
            initial_prompt=self.initial_prompt,
            vad_filter=True,
        )
        return " ".join(s.text.strip() for s in segments).strip()
