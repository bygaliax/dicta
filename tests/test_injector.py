"""Tests del inyector con win32 mockeado (sin tocar clipboard ni teclado reales)."""
import pytest

import dicta.injector as injector


class _Calls:
    def __init__(self):
        self.keys = []


@pytest.fixture
def fake_win32(monkeypatch):
    calls = _Calls()
    monkeypatch.setattr(injector, "_get_clipboard_text", lambda: "previo")
    monkeypatch.setattr(injector, "_set_clipboard_text", lambda t: None)
    monkeypatch.setattr(injector.win32gui, "IsWindow", lambda h: True)
    monkeypatch.setattr(injector.win32gui, "SetForegroundWindow", lambda h: None)
    monkeypatch.setattr(
        injector.win32api, "keybd_event",
        lambda vk, sc, flags, extra: calls.keys.append((vk, flags)),
    )
    monkeypatch.setattr(injector.time, "sleep", lambda s: None)
    return calls


def test_sin_enter_no_manda_return(fake_win32):
    assert injector.inject("hola", 42) is True
    vks = [vk for vk, _ in fake_win32.keys]
    assert injector.win32con.VK_RETURN not in vks


def test_con_enter_manda_return_tras_el_paste(fake_win32):
    assert injector.inject("hola", 42, send_enter=True) is True
    vks = [vk for vk, _ in fake_win32.keys]
    assert injector.win32con.VK_RETURN in vks
    assert vks.index(injector.win32con.VK_RETURN) > vks.index(ord("V"))


def test_enter_no_se_manda_si_no_hay_ventana(fake_win32, monkeypatch):
    monkeypatch.setattr(injector.win32gui, "IsWindow", lambda h: False)
    assert injector.inject("hola", 42, send_enter=True) is False
    assert fake_win32.keys == []
