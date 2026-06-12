"""Calibración EN VIVO del wake word (necesita micrófono — no es test automático).

Uso:
    .venv\\Scripts\\python.exe tests\\manual_wakeword_live.py

Reproduce el camino real del detector (misma gramática con señuelos y SetWords) y,
por cada resultado FINAL de Vosk, registra el texto y las palabras con su confianza.
Marca "FIRE" cuando una palabra == 'claude' supera el umbral. Escribe TODO también
a wake_calibration.log en la raíz del repo, para revisarlo después sin copiar/pegar.

Qué probar (di cada cosa 3-4 veces, con pausas):
  - "claude"            -> debería FIRE
  - "claro" / "clave"   -> NO debería FIRE
  - habla normal cerca  -> NO debería FIRE

Ctrl+C para salir.
"""
import json
import os
import queue
import sys
from pathlib import Path

import numpy as np
import sounddevice as sd
from vosk import KaldiRecognizer, Model, SetLogLevel

sys.path.insert(0, str(Path(__file__).parent.parent))

from dicta.wakeword import DECOYS, SAMPLE_RATE  # noqa: E402

WORD = "claude"
MIN_CONF = 0.85
MODEL = Path(os.environ["APPDATA"]) / "dicta" / "models" / "vosk-model-small-es-0.42"
LOG = Path(__file__).parent.parent / "wake_calibration.log"

SetLogLevel(-1)
grammar = [WORD, *DECOYS, "[unk]"]
rec = KaldiRecognizer(Model(str(MODEL)), SAMPLE_RATE, json.dumps(grammar))
rec.SetWords(True)

q: queue.Queue = queue.Queue()
log_f = LOG.open("w", encoding="utf-8")


def emit(line: str) -> None:
    print(line, flush=True)
    log_f.write(line + "\n")
    log_f.flush()


def on_audio(indata, frames, time_info, status):
    q.put(indata[:, 0].copy())


emit(f"# gramática={grammar} umbral={MIN_CONF}")
emit("# escuchando… di 'claude', luego 'claro'/'clave', luego habla normal. Ctrl+C para salir.")

with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", callback=on_audio):
    try:
        while True:
            chunk = q.get()
            pcm = (np.clip(chunk, -1, 1) * 32767).astype("int16").tobytes()
            if not rec.AcceptWaveform(pcm):
                continue
            data = json.loads(rec.Result())
            text = (data.get("text") or "").strip()
            words = data.get("result") or []
            if not text and not words:
                continue
            detail = ", ".join(f"{w['word']}={w['conf']:.2f}" for w in words)
            fire = any(w["word"] == WORD and w["conf"] >= MIN_CONF for w in words)
            emit(f"{'FIRE   ' if fire else '       '} text='{text}' | {detail}")
            if fire:
                rec.Reset()
    except KeyboardInterrupt:
        emit("# fin")
    finally:
        log_f.close()
