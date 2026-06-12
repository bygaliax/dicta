"""Tests del bus de audio con un InputStream falso (sin micrófono real)."""
import numpy as np
import pytest

import dicta.audio as audio


class FakeStream:
    instances = []

    def __init__(self, samplerate, channels, dtype, callback):
        self.callback = callback
        self.started = False
        self.closed = False
        self.active = False
        FakeStream.instances.append(self)

    def start(self):
        self.started = True
        self.active = True

    def stop(self):
        self.started = False
        self.active = False

    def close(self):
        self.closed = True

    def feed(self, n=160):
        data = np.ones((n, 1), dtype="float32") * 0.5
        self.callback(data, n, None, None)


@pytest.fixture
def bus(monkeypatch):
    FakeStream.instances = []
    monkeypatch.setattr(audio.sd, "InputStream", FakeStream)
    return audio.AudioBus()


def test_abre_con_el_primero_y_cierra_con_el_ultimo(bus):
    a, b = lambda c: None, lambda c: None
    bus.subscribe(a)
    assert len(FakeStream.instances) == 1
    bus.subscribe(b)
    assert len(FakeStream.instances) == 1  # mismo stream
    bus.unsubscribe(a)
    assert not FakeStream.instances[0].closed
    bus.unsubscribe(b)
    assert FakeStream.instances[0].closed


def test_reparte_chunks_1d_a_todos(bus):
    got_a, got_b = [], []
    bus.subscribe(got_a.append)
    bus.subscribe(got_b.append)
    FakeStream.instances[0].feed()
    assert len(got_a) == 1 and len(got_b) == 1
    assert got_a[0].ndim == 1


def test_un_suscriptor_roto_no_afecta_al_resto(bus):
    got = []

    def roto(chunk):
        raise RuntimeError("boom")

    bus.subscribe(roto)
    bus.subscribe(got.append)
    FakeStream.instances[0].feed()
    assert len(got) == 1


def test_suscribir_dos_veces_no_duplica(bus):
    got = []
    bus.subscribe(got.append)
    bus.subscribe(got.append)
    FakeStream.instances[0].feed()
    assert len(got) == 1


def test_recorder_graba_entre_start_y_stop(bus):
    from dicta.recorder import Recorder

    rec = Recorder(bus)
    rec.start()
    FakeStream.instances[0].feed()
    FakeStream.instances[0].feed()
    out = rec.stop()
    assert out.shape == (320,)
    assert FakeStream.instances[0].closed  # ya no queda nadie suscrito


def test_recorder_stop_sin_audio_devuelve_vacio(bus):
    from dicta.recorder import Recorder

    rec = Recorder(bus)
    rec.start()
    out = rec.stop()
    assert out.shape == (0,)


def test_recorder_discard_tira_el_audio(bus):
    from dicta.recorder import Recorder

    rec = Recorder(bus)
    rec.start()
    FakeStream.instances[0].feed()
    rec.discard()
    rec.start()
    out = rec.stop()
    assert out.shape == (0,)


def test_stream_muerto_se_reabre_al_suscribir(bus):
    primero = lambda c: None
    bus.subscribe(primero)
    FakeStream.instances[0].active = False  # el micro se desconectó en vuelo

    segundo = lambda c: None
    bus.subscribe(segundo)
    assert len(FakeStream.instances) == 2   # stream nuevo abierto
    assert FakeStream.instances[0].closed   # el muerto se descartó
    assert FakeStream.instances[1].started
