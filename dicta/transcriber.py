"""Whisper local vía faster-whisper. CUDA float16; fallback a CPU int8."""
import os
import sys
import sysconfig
from pathlib import Path

import numpy as np


def find_cuda_dll_dirs(nvidia_dir: Path) -> list[Path]:
    """Carpetas */bin de las wheels de NVIDIA (cublas, cudnn…) bajo site-packages/nvidia."""
    if not nvidia_dir.is_dir():
        return []
    return sorted(d for d in nvidia_dir.glob("*/bin") if d.is_dir())


def _register_cuda_dlls() -> None:
    """CTranslate2 en Windows no encuentra cublas/cudnn solo: añadirlas a la búsqueda de DLLs."""
    if sys.platform != "win32":
        return
    nvidia_dir = Path(sysconfig.get_paths()["purelib"]) / "nvidia"
    for bin_dir in find_cuda_dll_dirs(nvidia_dir):
        os.add_dll_directory(str(bin_dir))
        os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")


def build_initial_prompt(vocabulario: list[str]) -> str | None:
    if not vocabulario:
        return None
    return "Transcripción técnica. Vocabulario: " + ", ".join(vocabulario) + "."


class Transcriber:
    def __init__(self, model: str, language: str, vocabulario: list[str]) -> None:
        _register_cuda_dlls()
        from faster_whisper import WhisperModel  # import perezoso: tarda y pesa

        self.language = language
        self.initial_prompt = build_initial_prompt(vocabulario)
        try:
            self.model = WhisperModel(model, device="cuda", compute_type="float16")
            self.device = "cuda"
        except Exception as exc:
            print(f"CUDA no disponible ({exc}); usando CPU int8.", file=sys.stderr)
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
