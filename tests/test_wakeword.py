"""Tests del wake word con recognizer falso (sin Vosk ni modelo reales)."""
import zipfile
from pathlib import Path

import numpy as np

import dicta.wakeword as wakeword
from dicta.wakeword import MODEL_NAME, WakeWordDetector, ensure_model, heard_word

CHUNK = np.zeros(800, dtype="float32")


class FakeRecognizer:
    def __init__(self, partials):
        self.partials = list(partials)
        self.resets = 0

    def AcceptWaveform(self, pcm):
        return False

    def PartialResult(self):
        return self.partials.pop(0)

    def Reset(self):
        self.resets += 1


def make_detector(partials, fired):
    clock = {"t": 100.0}
    rec = FakeRecognizer(partials)
    det = WakeWordDetector(
        Path("."), "claude", lambda: fired.append(1),
        now=lambda: clock["t"], recognizer=rec,
    )
    det.set_armed(True)
    return det, rec, clock


def test_heard_word_en_parcial_y_final():
    assert heard_word('{"partial": "claude"}', "claude")
    assert heard_word('{"text": "claude"}', "claude")
    assert not heard_word('{"partial": "[unk]"}', "claude")
    assert not heard_word("esto no es json", "claude")


def test_dispara_una_vez_y_resetea_el_recognizer():
    fired = []
    det, rec, _ = make_detector(['{"partial": "claude"}', '{"partial": "claude"}'], fired)
    det._process(CHUNK)
    det._process(CHUNK)
    assert fired == [1]  # el segundo cae dentro del debounce
    assert rec.resets == 1


def test_tras_el_debounce_vuelve_a_disparar():
    fired = []
    det, _, clock = make_detector(['{"partial": "claude"}', '{"partial": "claude"}'], fired)
    det._process(CHUNK)
    clock["t"] += 2.0
    det._process(CHUNK)
    assert fired == [1, 1]


def test_ensure_model_no_descarga_si_ya_existe(tmp_path):
    (tmp_path / MODEL_NAME).mkdir()
    # sin red: si intentara descargar, urlretrieve real fallaría o tardaría
    assert ensure_model(tmp_path) == tmp_path / MODEL_NAME


def test_ensure_model_descarga_y_extrae(tmp_path, monkeypatch):
    def fake_download(url, dest):
        with zipfile.ZipFile(dest, "w") as zf:
            zf.writestr(f"{MODEL_NAME}/README", "modelo")

    monkeypatch.setattr(wakeword.urllib.request, "urlretrieve", fake_download)
    path = ensure_model(tmp_path)
    assert (path / "README").exists()
    assert not (tmp_path / f"{MODEL_NAME}.zip").exists()  # zip limpiado
