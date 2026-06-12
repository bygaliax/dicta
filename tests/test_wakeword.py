"""Tests del wake word con recognizer falso (sin Vosk ni modelo reales)."""
import zipfile
from pathlib import Path

import numpy as np

import dicta.wakeword as wakeword
from dicta.wakeword import MODEL_NAME, WakeWordDetector, ensure_model, heard_word

CHUNK = np.zeros(800, dtype="float32")


class FakeRecognizer:
    """Cada paso es (acepta_final: bool, json: str) que _process consume en orden."""

    def __init__(self, steps):
        self.steps = list(steps)
        self.resets = 0
        self._pending = ""

    def AcceptWaveform(self, pcm):
        accept, payload = self.steps.pop(0)
        self._pending = payload
        return accept

    def Result(self):
        return self._pending

    def Reset(self):
        self.resets += 1


FINAL_OK = (True, '{"result": [{"word": "claude", "conf": 0.95}], "text": "claude"}')
FINAL_BAJO = (True, '{"result": [{"word": "claude", "conf": 0.40}], "text": "claude"}')
PARCIAL = (False, '{"partial": "claude"}')


def make_detector(steps, fired, min_conf=0.85):
    clock = {"t": 100.0}
    rec = FakeRecognizer(steps)
    det = WakeWordDetector(
        Path("."), "claude", lambda: fired.append(1),
        now=lambda: clock["t"], recognizer=rec, min_conf=min_conf,
    )
    det.set_armed(True)
    return det, rec, clock


def test_heard_word_usa_conf_del_resultado_final():
    assert heard_word('{"result": [{"word": "claude", "conf": 0.95}]}', "claude", 0.85)
    assert not heard_word('{"result": [{"word": "claude", "conf": 0.40}]}', "claude", 0.85)
    assert not heard_word('{"result": [{"word": "claro", "conf": 0.99}]}', "claude", 0.85)
    assert not heard_word("esto no es json", "claude", 0.85)


def test_heard_word_respaldo_por_texto_sin_array():
    # sin 'result' (recognizer sin SetWords): respaldo laxo por texto
    assert heard_word('{"text": "claude"}', "claude", 0.85)


def test_no_dispara_en_parcial():
    fired = []
    det, _, _ = make_detector([PARCIAL, PARCIAL], fired)
    det._process(CHUNK)
    det._process(CHUNK)
    assert fired == []  # los parciales se ignoran del todo


def test_no_dispara_bajo_umbral():
    fired = []
    det, _, _ = make_detector([FINAL_BAJO], fired)
    det._process(CHUNK)
    assert fired == []


def test_dispara_una_vez_y_resetea_el_recognizer():
    fired = []
    det, rec, _ = make_detector([FINAL_OK, FINAL_OK], fired)
    det._process(CHUNK)
    det._process(CHUNK)
    assert fired == [1]  # el segundo cae dentro del debounce
    assert rec.resets == 1


def test_tras_el_debounce_vuelve_a_disparar():
    fired = []
    det, _, clock = make_detector([FINAL_OK, FINAL_OK], fired)
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
