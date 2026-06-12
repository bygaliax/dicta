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
