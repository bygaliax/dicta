import threading
import time

import numpy as np

from dicta.speaker import Speaker


def _synth_ok(text):
    return np.zeros(2048, dtype=np.float32), 24000


def test_speak_sintetiza_reproduce_y_avisa_al_terminar():
    llamadas = {}
    done = threading.Event()

    def player(samples, sr, stop, on_level):
        llamadas["played"] = (len(samples), sr)
        on_level(0.2)

    niveles = []
    sp = Speaker(_synth_ok, player, niveles.append, done.set)
    assert sp.speak("hola") is True
    assert done.wait(2.0)
    assert llamadas["played"] == (2048, 24000)
    assert niveles == [0.2]


def test_speak_rechaza_si_ya_esta_hablando():
    empezo = threading.Event()
    suelta = threading.Event()

    def player(samples, sr, stop, on_level):
        empezo.set()
        suelta.wait(2.0)

    sp = Speaker(_synth_ok, player, lambda l: None, lambda: None)
    assert sp.speak("uno") is True
    assert empezo.wait(2.0)
    assert sp.speak("dos") is False
    suelta.set()


def test_stop_corta_y_on_done_se_dispara_igualmente():
    done = threading.Event()

    def player(samples, sr, stop, on_level):
        # reproduce "por bloques" hasta que stop se active
        for _ in range(100):
            if stop.is_set():
                return
            time.sleep(0.01)

    sp = Speaker(_synth_ok, player, lambda l: None, done.set)
    sp.speak("largo")
    time.sleep(0.05)
    sp.stop()
    assert done.wait(2.0)


def test_error_de_sintesis_dispara_on_done_sin_reventar():
    done = threading.Event()

    def synth_roto(text):
        raise RuntimeError("kokoro caput")

    sp = Speaker(synth_roto, lambda *a: None, lambda l: None, done.set)
    assert sp.speak("hola") is True
    assert done.wait(2.0)
