"""Tests del corte por silencio con un VAD falso (sin faster-whisper)."""
import numpy as np

from dicta.silence import SilenceDetector

CHUNK = np.zeros(8000, dtype="float32")  # 0.5 s exactos a 16 kHz


def detector(speech_seq, **kwargs):
    """has_speech falso: responde según una lista de bools, una por ventana."""
    it = iter(speech_seq)
    return SilenceDetector(has_speech=lambda w: next(it), **kwargs)


def test_voz_y_luego_silencio_dispara():
    d = detector([True, True, False, False, False, False], silence_s=2.0)
    events = [d.feed(CHUNK) for _ in range(6)]
    assert events == [None, None, None, None, None, "silence"]


def test_sin_voz_dispara_timeout_no_silence():
    d = detector([False] * 20, silence_s=2.0, timeout_s=3.0)
    events = [d.feed(CHUNK) for _ in range(6)]
    assert "silence" not in events
    assert events[5] == "timeout"


def test_voz_intermitente_reinicia_el_contador():
    d = detector([True, False, False, True, False, False, False, False], silence_s=2.0)
    events = [d.feed(CHUNK) for _ in range(8)]
    assert events[:7] == [None] * 7
    assert events[7] == "silence"


def test_tras_disparar_queda_inerte_hasta_reset():
    d = detector([True, False, False, False, False], silence_s=1.5)
    events = [d.feed(CHUNK) for _ in range(4)]
    assert events[3] == "silence"
    assert d.feed(CHUNK) is None  # inerte: ni siquiera consume el VAD


def test_chunks_pequenos_se_acumulan_hasta_la_ventana():
    d = detector([True], silence_s=2.0)
    small = np.zeros(1600, dtype="float32")  # 0.1 s
    for _ in range(4):
        assert d.feed(small) is None
    d.feed(small)  # completa los 0.5 s: consulta el VAD sin reventar
