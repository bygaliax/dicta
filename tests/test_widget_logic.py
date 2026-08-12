"""Lógica pura del widget (sin Qt)."""
from dicta.widget import wave_scale


def test_wave_scale_reposo_pico_y_vuelta():
    assert wave_scale(0.0) == 0.4          # arranque en reposo
    assert abs(wave_scale(0.12) - 0.95) < 1e-9  # pico
    assert wave_scale(0.28) == 0.4         # vuelta al reposo
    assert wave_scale(0.6) == 0.4          # resto del ciclo, quieto
    assert abs(wave_scale(1.12) - wave_scale(0.12)) < 1e-9  # periódica (con epsilon: % 1.0 no es exacto)


def test_speaking_tiene_estilo_y_tooltip():
    from dicta.state import State
    from dicta.widget import _STYLES, _TIPS, PILL_W, _INK, _IVORY

    bg, fg, mode, width = _STYLES[State.SPEAKING]
    assert (bg, fg) == (_IVORY, _INK)
    assert mode == "bars-live"
    assert width == PILL_W
    assert State.SPEAKING in _TIPS
