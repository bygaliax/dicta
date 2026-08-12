# tests/test_state.py
from dicta.state import State, StateMachine


def make_sm():
    sm = StateMachine()
    events = []
    sm.on_change.append(lambda s: events.append(s))
    sm.on_start_listening.append(lambda: events.append("START_REC"))
    sm.on_stop_listening.append(lambda: events.append("STOP_REC"))
    return sm, events


def test_arranca_en_loading():
    sm, _ = make_sm()
    assert sm.state is State.LOADING


def test_click_en_loading_se_ignora():
    sm, events = make_sm()
    sm.click()
    assert sm.state is State.LOADING
    assert events == []


def test_ciclo_completo_dictado():
    sm, events = make_sm()
    sm.model_ready()
    sm.click()   # IDLE -> LISTENING
    sm.click()   # LISTENING -> TRANSCRIBING
    sm.transcription_done()
    assert events == [State.IDLE, State.LISTENING, "START_REC",
                      State.TRANSCRIBING, "STOP_REC", State.IDLE]


def test_click_en_transcribing_se_ignora():
    sm, _ = make_sm()
    sm.model_ready()
    sm.click()
    sm.click()
    sm.click()  # ignorado
    assert sm.state is State.TRANSCRIBING


def test_error_y_recuperacion_con_click():
    sm, _ = make_sm()
    sm.model_ready()
    sm.fail()
    assert sm.state is State.ERROR
    sm.click()
    assert sm.state is State.IDLE


def make_sm_ml():
    sm = StateMachine(handsfree_enabled=True)
    events = []
    sm.on_change.append(lambda s: events.append(s))
    sm.on_start_listening.append(lambda: events.append("START_REC"))
    sm.on_stop_listening.append(lambda: events.append("STOP_REC"))
    sm.on_cancel_listening.append(lambda: events.append("CANCEL_REC"))
    return sm, events


def test_model_ready_va_a_armed_con_manos_libres():
    sm, _ = make_sm_ml()
    sm.model_ready()
    assert sm.state is State.ARMED


def test_wake_inicia_sesion_manos_libres():
    sm, events = make_sm_ml()
    sm.model_ready()
    sm.wake_detected()
    assert sm.state is State.LISTENING
    assert sm.session_handsfree is True
    assert "START_REC" in events


def test_click_desde_armed_inicia_sesion_manual():
    sm, _ = make_sm_ml()
    sm.model_ready()
    sm.click()
    assert sm.state is State.LISTENING
    assert sm.session_handsfree is False


def test_silencio_solo_corta_sesiones_manos_libres():
    sm, _ = make_sm_ml()
    sm.model_ready()
    sm.click()             # sesión manual
    sm.silence_detected()  # ignorado
    assert sm.state is State.LISTENING


def test_silencio_corta_sesion_wake():
    sm, _ = make_sm_ml()
    sm.model_ready()
    sm.wake_detected()
    sm.silence_detected()
    assert sm.state is State.TRANSCRIBING


def test_wake_ignorado_fuera_de_armed():
    sm, _ = make_sm_ml()
    sm.model_ready()
    sm.wake_detected()
    sm.wake_detected()  # ya escuchando: ignorado
    assert sm.state is State.LISTENING


def test_cancel_vuelve_a_armed_sin_transcribir():
    sm, events = make_sm_ml()
    sm.model_ready()
    sm.wake_detected()
    sm.cancel()
    assert sm.state is State.ARMED
    assert "CANCEL_REC" in events
    assert "STOP_REC" not in events


def test_toggle_handsfree_alterna_idle_armed():
    sm, _ = make_sm_ml()
    sm.model_ready()
    sm.toggle_handsfree()
    assert sm.state is State.IDLE
    sm.toggle_handsfree()
    assert sm.state is State.ARMED


def test_transcription_done_vuelve_a_armed():
    sm, _ = make_sm_ml()
    sm.model_ready()
    sm.wake_detected()
    sm.silence_detected()
    sm.transcription_done()
    assert sm.state is State.ARMED


def test_error_se_recupera_a_armed_con_click():
    sm, _ = make_sm_ml()
    sm.model_ready()
    sm.fail()
    sm.click()
    assert sm.state is State.ARMED


def test_cancel_ignorado_en_sesion_manual():
    sm, events = make_sm_ml()
    sm.model_ready()
    sm.click()   # sesión manual
    sm.cancel()  # solo aplica a manos libres: no-op
    assert sm.state is State.LISTENING
    assert "CANCEL_REC" not in events


def test_fail_resetea_session_handsfree():
    sm, _ = make_sm_ml()
    sm.model_ready()
    sm.wake_detected()
    sm.fail()
    assert sm.session_handsfree is False


# --- v3: voz de salida ---

def make_sm_voz():
    sm = StateMachine(handsfree_enabled=True)
    events = []
    sm.on_change.append(lambda s: events.append(s))
    sm.on_start_listening.append(lambda: events.append("START_REC"))
    sm.on_stop_speaking.append(lambda: events.append("STOP_SPEAK"))
    sm.model_ready()
    events.clear()
    return sm, events


def test_speak_request_desde_armed():
    sm, _ = make_sm_voz()
    assert sm.speak_request(abre_mic=False) is True
    assert sm.state is State.SPEAKING


def test_speak_request_desde_idle():
    sm = StateMachine(handsfree_enabled=False)
    sm.model_ready()
    assert sm.speak_request(abre_mic=False) is True
    assert sm.state is State.SPEAKING


def test_speak_request_rechazado_si_dictando():
    sm, _ = make_sm_voz()
    sm.wake_detected()
    assert sm.speak_request(abre_mic=False) is False
    assert sm.state is State.LISTENING


def test_speak_request_rechazado_si_transcribiendo():
    sm, _ = make_sm_voz()
    sm.wake_detected()
    sm.silence_detected()
    assert sm.speak_request(abre_mic=True) is False
    assert sm.state is State.TRANSCRIBING


def test_speak_done_sin_pregunta_vuelve_a_reposo():
    sm, events = make_sm_voz()
    sm.speak_request(abre_mic=False)
    sm.speak_done()
    assert sm.state is State.ARMED
    assert "START_REC" not in events


def test_speak_done_con_pregunta_abre_escucha_manos_libres():
    sm, events = make_sm_voz()
    sm.speak_request(abre_mic=True)
    sm.speak_done()
    assert sm.state is State.LISTENING
    assert sm.session_handsfree is True
    assert "START_REC" in events


def test_click_durante_speaking_corta_y_abre_escucha():
    sm, events = make_sm_voz()
    sm.speak_request(abre_mic=False)
    events.clear()
    sm.click()
    assert events == ["STOP_SPEAK", State.LISTENING, "START_REC"]
    assert sm.session_handsfree is True


def test_speak_done_tras_click_es_noop():
    # El stop() del speaker dispara on_done igualmente; no debe romper nada.
    sm, _ = make_sm_voz()
    sm.speak_request(abre_mic=True)
    sm.click()
    sm.speak_done()
    assert sm.state is State.LISTENING


def test_wake_ignorado_durante_speaking():
    sm, _ = make_sm_voz()
    sm.speak_request(abre_mic=False)
    sm.wake_detected()
    assert sm.state is State.SPEAKING


def test_fail_durante_speaking_va_a_error():
    sm, _ = make_sm_voz()
    sm.speak_request(abre_mic=False)
    sm.fail()
    assert sm.state is State.ERROR
