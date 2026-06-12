# dicta v2 — Manos libres, cápsula viva y fix z-order · Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wake word "Claude" con dictado manos libres (corte por silencio + Enter automático en la terminal), rediseño del widget a "ecualizador en calma" con cápsula expandible, y fix del z-order (el botón vive justo encima de la terminal, no flota sobre otras apps).

**Architecture:** Spec aprobado en `docs/superpowers/specs/2026-06-12-dicta-v2-manos-libres-design.md`. Un `AudioBus` comparte un único `InputStream` de 16 kHz entre wake word (Vosk en modo gramática, hilo propio), grabadora y detector de silencio (VAD de faster-whisper). La máquina de estados pura gana `ARMED` y un flag `session_handsfree` que decide VAD, destino del paste y Enter automático. El widget pinta barras de ecualizador en una forma que se estira de círculo (52px) a cápsula (116px) dentro de una ventana de tamaño fijo anclada por el borde derecho.

**Tech Stack:** Python 3.12, PyQt6, faster-whisper (Whisper + Silero VAD), Vosk (`vosk-model-small-es-0.42`), sounddevice, pywin32, pytest.

**Rama:** `feature/widget-dock-anim` (continuar ahí; ya contiene docking).
**Regla del repo:** commits locales sí; **nunca `git push` sin OK de Robert**.

---

## Estructura de archivos

| Archivo | Acción | Responsabilidad |
|---|---|---|
| `dicta/config.py` | Modificar | Sección `[manos_libres]` |
| `dicta/state.py` | Modificar | Estado `ARMED`, eventos wake/silencio/cancel/toggle |
| `dicta/injector.py` | Modificar | Parámetro `send_enter` |
| `dicta/audio.py` | Crear | Bus de audio compartido |
| `dicta/recorder.py` | Modificar | Grabar suscrito al bus + `discard()` |
| `dicta/silence.py` | Crear | Corte por silencio (VAD inyectable) |
| `dicta/wakeword.py` | Crear | Vosk gramática + descarga de modelo |
| `dicta/widget.py` | Modificar (reescritura) | Ecualizador en calma / cápsula |
| `dicta/docking.py` | Modificar | `place_above` (z-order) |
| `dicta/app.py` | Modificar | Cableado completo |
| `config.example.toml`, `pyproject.toml`, `docs/manual-test-checklist.md`, `README.md` | Modificar | Config, dep `vosk`, checklist |
| `tests/test_config.py`, `tests/test_state.py`, `tests/test_docking.py` | Modificar | Casos nuevos |
| `tests/test_injector.py`, `tests/test_audio.py`, `tests/test_silence.py`, `tests/test_wakeword.py` | Crear | Suites nuevas |
| `tests/manual_widget_demo.py` | Modificar | Demo con `ARMED` y nivel simulado |

Comando de tests (siempre desde `X:\Proyectos\dicta`, venv activo):
`.venv\Scripts\python -m pytest tests/ -v`

---

### Task 1: Config `[manos_libres]`

**Files:**
- Modify: `dicta/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Añadir tests que fallan** al final de `tests/test_config.py`:

```python
def test_manos_libres_defaults_sin_seccion(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text("[ui]\nsonidos = true\n", encoding="utf-8")
    cfg = load_config(p)
    assert cfg.manos_libres_activado is True
    assert cfg.wake_word == "claude"
    assert cfg.silencio_segundos == 2.0
    assert cfg.auto_enviar is True


def test_manos_libres_personalizado(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text(
        '[manos_libres]\nactivado = false\npalabra = "Compu"\n'
        "silencio_segundos = 1.5\nauto_enviar = false\n",
        encoding="utf-8",
    )
    cfg = load_config(p)
    assert cfg.manos_libres_activado is False
    assert cfg.wake_word == "compu"  # normalizada a minúsculas
    assert cfg.silencio_segundos == 1.5
    assert cfg.auto_enviar is False
```

(Si el archivo no importa ya `load_config`, usar `from dicta.config import load_config`.)

- [ ] **Step 2: Verificar que fallan**

Run: `.venv\Scripts\python -m pytest tests/test_config.py -v`
Expected: FAIL con `AttributeError: ... 'manos_libres_activado'`

- [ ] **Step 3: Implementar.** En `dicta/config.py`, añadir al final del dataclass `Config`:

```python
    manos_libres_activado: bool = True
    wake_word: str = "claude"
    silencio_segundos: float = 2.0
    auto_enviar: bool = True
```

Y en `load_config()`, junto a las demás secciones:

```python
    ml = data.get("manos_libres", {})
    cfg.manos_libres_activado = bool(ml.get("activado", cfg.manos_libres_activado))
    cfg.wake_word = str(ml.get("palabra", cfg.wake_word)).strip().lower()
    cfg.silencio_segundos = float(ml.get("silencio_segundos", cfg.silencio_segundos))
    cfg.auto_enviar = bool(ml.get("auto_enviar", cfg.auto_enviar))
```

- [ ] **Step 4: Verificar que pasan**

Run: `.venv\Scripts\python -m pytest tests/test_config.py -v`
Expected: PASS (todos)

- [ ] **Step 5: Commit**

```bash
git add dicta/config.py tests/test_config.py
git commit -m "feat: config [manos_libres] (activado, palabra, silencio, auto_enviar)"
```

---

### Task 2: Máquina de estados — `ARMED` y sesiones manos libres

**Files:**
- Modify: `dicta/state.py`
- Test: `tests/test_state.py`

- [ ] **Step 1: Tests que fallan.** Añadir al final de `tests/test_state.py`:

```python
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
```

- [ ] **Step 2: Verificar que fallan**

Run: `.venv\Scripts\python -m pytest tests/test_state.py -v`
Expected: FAIL (`TypeError: ... handsfree_enabled` / `AttributeError: ARMED`). Los tests viejos deben seguir PASS.

- [ ] **Step 3: Implementar.** Reemplazar `dicta/state.py` por:

```python
"""Máquina de estados pura (sin Qt). El widget pinta según on_change;
la app arranca/para la grabadora según on_start/stop/cancel_listening.
`session_handsfree` marca si la sesión actual la inició el wake word:
decide VAD, destino del paste y Enter automático (en app.py)."""
import sys
from enum import Enum, auto
from typing import Callable


class State(Enum):
    LOADING = auto()
    IDLE = auto()         # manos libres OFF
    ARMED = auto()        # esperando el wake word
    LISTENING = auto()
    TRANSCRIBING = auto()
    ERROR = auto()


class StateMachine:
    def __init__(self, handsfree_enabled: bool = False) -> None:
        self.state = State.LOADING
        self.handsfree_enabled = handsfree_enabled
        self.session_handsfree = False
        self.on_change: list[Callable[[State], None]] = []
        self.on_start_listening: list[Callable[[], None]] = []
        self.on_stop_listening: list[Callable[[], None]] = []
        self.on_cancel_listening: list[Callable[[], None]] = []

    def _set(self, state: State) -> None:
        self.state = state
        self._dispatch(self.on_change, state)

    @staticmethod
    def _dispatch(callbacks: list, *args) -> None:
        """Un callback que falla no debe impedir los siguientes."""
        for cb in callbacks:
            try:
                cb(*args)
            except Exception as exc:
                print(f"Error en callback de estado: {exc}", file=sys.stderr)

    def _resting(self) -> State:
        return State.ARMED if self.handsfree_enabled else State.IDLE

    def model_ready(self) -> None:
        if self.state is State.LOADING:
            self._set(self._resting())

    def click(self) -> None:
        if self.state in (State.IDLE, State.ARMED):
            self.session_handsfree = False
            self._set(State.LISTENING)
            self._dispatch(self.on_start_listening)
        elif self.state is State.LISTENING:
            self._set(State.TRANSCRIBING)
            self._dispatch(self.on_stop_listening)
        elif self.state is State.ERROR:
            self._set(self._resting())
        # LOADING y TRANSCRIBING ignoran clicks

    def wake_detected(self) -> None:
        if self.state is State.ARMED:
            self.session_handsfree = True
            self._set(State.LISTENING)
            self._dispatch(self.on_start_listening)

    def silence_detected(self) -> None:
        if self.state is State.LISTENING and self.session_handsfree:
            self._set(State.TRANSCRIBING)
            self._dispatch(self.on_stop_listening)

    def cancel(self) -> None:
        """Aborta el dictado sin transcribir (timeout sin voz)."""
        if self.state is State.LISTENING:
            self._set(self._resting())
            self._dispatch(self.on_cancel_listening)

    def toggle_handsfree(self) -> None:
        self.handsfree_enabled = not self.handsfree_enabled
        if self.state in (State.IDLE, State.ARMED):
            self._set(self._resting())

    def transcription_done(self) -> None:
        if self.state is State.TRANSCRIBING:
            self._set(self._resting())

    def fail(self) -> None:
        if self.state is not State.ERROR:
            self._set(State.ERROR)
```

- [ ] **Step 4: Verificar que pasan (viejos y nuevos)**

Run: `.venv\Scripts\python -m pytest tests/test_state.py -v`
Expected: PASS (todos)

- [ ] **Step 5: Commit**

```bash
git add dicta/state.py tests/test_state.py
git commit -m "feat: estado ARMED y sesiones manos libres en la maquina de estados"
```

---

### Task 3: Injector — `send_enter`

**Files:**
- Modify: `dicta/injector.py`
- Test: `tests/test_injector.py` (crear)

- [ ] **Step 1: Test que falla.** Crear `tests/test_injector.py`:

```python
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
```

- [ ] **Step 2: Verificar que falla**

Run: `.venv\Scripts\python -m pytest tests/test_injector.py -v`
Expected: FAIL con `TypeError: inject() got an unexpected keyword argument 'send_enter'`

- [ ] **Step 3: Implementar.** En `dicta/injector.py`, cambiar la firma y añadir el Enter tras el paste (antes de restaurar el clipboard):

```python
def inject(
    text: str,
    target_hwnd: int | None,
    paste_shortcut: str = "ctrl+v",
    send_enter: bool = False,
) -> bool:
```

Y dentro, después de `time.sleep(0.3)  # dar tiempo al paste...` y antes del bloque `if previous is not None:`:

```python
        if send_enter:
            win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)
            win32api.keybd_event(win32con.VK_RETURN, 0, win32con.KEYEVENTF_KEYUP, 0)
            time.sleep(0.08)
```

Actualizar el docstring de la función: añadir la línea `Con send_enter=True manda Enter tras pegar (envío directo, solo manos libres).`

- [ ] **Step 4: Verificar que pasa**

Run: `.venv\Scripts\python -m pytest tests/test_injector.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add dicta/injector.py tests/test_injector.py
git commit -m "feat: inject() acepta send_enter para el envio directo"
```

---

### Task 4: AudioBus — un solo stream compartido

**Files:**
- Create: `dicta/audio.py`
- Test: `tests/test_audio.py` (crear)

- [ ] **Step 1: Tests que fallan.** Crear `tests/test_audio.py`:

```python
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
        FakeStream.instances.append(self)

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

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
```

- [ ] **Step 2: Verificar que fallan**

Run: `.venv\Scripts\python -m pytest tests/test_audio.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'dicta.audio'`

- [ ] **Step 3: Implementar.** Crear `dicta/audio.py`:

```python
"""Bus de audio compartido: un solo InputStream de 16 kHz mono float32 para
wake word, grabadora y VAD a la vez (sin pelearse por el micrófono).
Se abre con el primer suscriptor y se cierra con el último. Los callbacks
reciben cada chunk como np.ndarray 1-D float32 — ¡desde el hilo de audio!
(nada pesado ahí: encolar o acumular y volver)."""
import threading

import sounddevice as sd

SAMPLE_RATE = 16000


class AudioBus:
    def __init__(self) -> None:
        self._subs: list = []
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()

    def subscribe(self, callback) -> None:
        """Puede lanzar si el micrófono falla al abrir el stream."""
        with self._lock:
            if callback in self._subs:
                return
            self._subs.append(callback)
            if self._stream is None:
                try:
                    self._open()
                except Exception:
                    self._subs.remove(callback)
                    raise

    def unsubscribe(self, callback) -> None:
        with self._lock:
            if callback in self._subs:
                self._subs.remove(callback)
            if not self._subs and self._stream is not None:
                self._stream.stop()
                self._stream.close()
                self._stream = None

    def _open(self) -> None:
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            callback=self._on_audio,
        )
        try:
            self._stream.start()
        except Exception:
            self._stream.close()
            self._stream = None
            raise

    def _on_audio(self, indata, frames, time_info, status) -> None:
        chunk = indata[:, 0].copy()
        for cb in list(self._subs):
            try:
                cb(chunk)
            except Exception:
                pass  # un suscriptor roto no debe tumbar el stream
```

- [ ] **Step 4: Verificar que pasan**

Run: `.venv\Scripts\python -m pytest tests/test_audio.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add dicta/audio.py tests/test_audio.py
git commit -m "feat: AudioBus compartido (un solo InputStream para todo)"
```

---

### Task 5: Recorder sobre el bus + `discard()`

**Files:**
- Modify: `dicta/recorder.py`
- Test: `tests/test_audio.py` (ampliar)

- [ ] **Step 1: Tests que fallan.** Añadir al final de `tests/test_audio.py`:

```python
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
```

- [ ] **Step 2: Verificar que fallan**

Run: `.venv\Scripts\python -m pytest tests/test_audio.py -v`
Expected: FAIL con `TypeError: Recorder.__init__() takes 1 positional argument`

- [ ] **Step 3: Implementar.** Reemplazar `dicta/recorder.py` por:

```python
"""Graba el dictado tomando chunks del AudioBus (16 kHz mono float32)."""
import numpy as np

from dicta.audio import AudioBus


class Recorder:
    def __init__(self, bus: AudioBus) -> None:
        self.bus = bus
        self._chunks: list[np.ndarray] = []
        self._active = False

    def start(self) -> None:
        """Puede lanzar si el micrófono falla (lo propaga el bus)."""
        self._chunks = []
        self._active = True
        try:
            self.bus.subscribe(self._on_chunk)
        except Exception:
            self._active = False
            raise

    def stop(self) -> np.ndarray:
        self._active = False
        self.bus.unsubscribe(self._on_chunk)
        chunks, self._chunks = self._chunks, []
        if not chunks:
            return np.zeros(0, dtype="float32")
        return np.concatenate(chunks)

    def discard(self) -> None:
        """Aborta sin devolver audio (timeout del manos libres)."""
        self._active = False
        self.bus.unsubscribe(self._on_chunk)
        self._chunks = []

    def _on_chunk(self, chunk: np.ndarray) -> None:
        if self._active:
            self._chunks.append(chunk)
```

- [ ] **Step 4: Verificar que pasan**

Run: `.venv\Scripts\python -m pytest tests/test_audio.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add dicta/recorder.py tests/test_audio.py
git commit -m "refactor: Recorder suscrito al AudioBus, con discard()"
```

---

### Task 6: SilenceDetector — corte por silencio

**Files:**
- Create: `dicta/silence.py`
- Test: `tests/test_silence.py` (crear)

- [ ] **Step 1: Tests que fallan.** Crear `tests/test_silence.py`:

```python
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
```

- [ ] **Step 2: Verificar que fallan**

Run: `.venv\Scripts\python -m pytest tests/test_silence.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'dicta.silence'`

- [ ] **Step 3: Implementar.** Crear `dicta/silence.py`:

```python
"""Corte por silencio para sesiones manos libres. Acumula audio en ventanas
de ~0.5 s y pregunta a un VAD si hay voz. Tras `silence_s` seguidos sin voz
(habiendo oído voz antes) devuelve "silence"; si nunca llega voz en
`timeout_s`, devuelve "timeout". El VAD es inyectable para tests; el real
reutiliza el Silero que ya trae faster-whisper (sin dependencia nueva)."""
import numpy as np

SAMPLE_RATE = 16000
WINDOW_S = 0.5


def _vad_has_speech(window: np.ndarray) -> bool:
    from faster_whisper.vad import VadOptions, get_speech_timestamps  # import perezoso

    return bool(get_speech_timestamps(window, VadOptions()))


class SilenceDetector:
    def __init__(
        self,
        silence_s: float = 2.0,
        timeout_s: float = 10.0,
        has_speech=_vad_has_speech,
    ) -> None:
        self.silence_s = silence_s
        self.timeout_s = timeout_s
        self.has_speech = has_speech
        self.reset()

    def reset(self) -> None:
        self._buffer: list[np.ndarray] = []
        self._buffered = 0
        self._heard_speech = False
        self._silence = 0.0
        self._elapsed = 0.0
        self._fired = False

    def feed(self, chunk: np.ndarray) -> str | None:
        """Devuelve "silence", "timeout" o None. Tras disparar queda inerte."""
        if self._fired:
            return None
        self._buffer.append(chunk)
        self._buffered += len(chunk)
        if self._buffered < SAMPLE_RATE * WINDOW_S:
            return None
        window = np.concatenate(self._buffer)
        self._buffer = []
        self._buffered = 0
        seconds = len(window) / SAMPLE_RATE
        self._elapsed += seconds
        if self.has_speech(window):
            self._heard_speech = True
            self._silence = 0.0
        else:
            self._silence += seconds
        if self._heard_speech and self._silence >= self.silence_s:
            self._fired = True
            return "silence"
        if not self._heard_speech and self._elapsed >= self.timeout_s:
            self._fired = True
            return "timeout"
        return None
```

- [ ] **Step 4: Verificar que pasan**

Run: `.venv\Scripts\python -m pytest tests/test_silence.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add dicta/silence.py tests/test_silence.py
git commit -m "feat: SilenceDetector (corte por silencio con VAD inyectable)"
```

---

### Task 7: Wake word — Vosk en modo gramática

**Files:**
- Create: `dicta/wakeword.py`
- Modify: `pyproject.toml`
- Test: `tests/test_wakeword.py` (crear)

- [ ] **Step 1: Añadir la dependencia.** En `pyproject.toml`, añadir a `dependencies`:

```toml
    "vosk>=0.3.45",
```

Run: `.venv\Scripts\pip install vosk`
Expected: instala vosk sin errores.

- [ ] **Step 2: Tests que fallan.** Crear `tests/test_wakeword.py`:

```python
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
```

- [ ] **Step 3: Verificar que fallan**

Run: `.venv\Scripts\python -m pytest tests/test_wakeword.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'dicta.wakeword'`

- [ ] **Step 4: Implementar.** Crear `dicta/wakeword.py`:

```python
"""Detector del wake word con Vosk en modo gramática: solo reconoce la
palabra configurada, el resto cae en [unk]. Se suscribe al AudioBus; el
trabajo pesado va en un hilo propio (el hilo de audio solo encola)."""
import json
import queue
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

import numpy as np

MODEL_NAME = "vosk-model-small-es-0.42"
MODEL_URL = f"https://alphacephei.com/vosk/models/{MODEL_NAME}.zip"
SAMPLE_RATE = 16000
DEBOUNCE_S = 1.0


def ensure_model(models_dir: Path) -> Path:
    """Devuelve la carpeta del modelo, descargándolo la primera vez (~39 MB)."""
    target = models_dir / MODEL_NAME
    if target.is_dir():
        return target
    models_dir.mkdir(parents=True, exist_ok=True)
    zip_path = models_dir / f"{MODEL_NAME}.zip"
    print(f"Descargando modelo de wake word ({MODEL_NAME}, ~39 MB)…")
    urllib.request.urlretrieve(MODEL_URL, zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(models_dir)
    zip_path.unlink()
    if not target.is_dir():
        raise RuntimeError(f"El zip no contenía {MODEL_NAME}")
    print("Modelo de wake word listo.")
    return target


def heard_word(result_json: str, word: str) -> bool:
    """True si el JSON de Vosk (parcial o final) contiene la palabra."""
    try:
        data = json.loads(result_json)
    except json.JSONDecodeError:
        return False
    text = data.get("partial") or data.get("text") or ""
    return word in text.split()


class WakeWordDetector:
    """feed() encola audio; un hilo lo pasa por Vosk y llama on_detect()
    (¡desde ese hilo!) al oír la palabra, con debounce de 1 s."""

    def __init__(
        self,
        model_dir: Path,
        word: str,
        on_detect,
        now=time.monotonic,
        recognizer=None,
    ) -> None:
        if recognizer is None:
            from vosk import KaldiRecognizer, Model, SetLogLevel  # import perezoso

            SetLogLevel(-1)
            recognizer = KaldiRecognizer(
                Model(str(model_dir)), SAMPLE_RATE, json.dumps([word, "[unk]"])
            )
        self.word = word
        self.on_detect = on_detect
        self._now = now
        self._recognizer = recognizer
        self._armed = False
        self._last_fire = -1e9
        self._queue: queue.Queue = queue.Queue(maxsize=64)
        threading.Thread(target=self._work, daemon=True).start()

    def set_armed(self, armed: bool) -> None:
        self._armed = armed

    def feed(self, chunk: np.ndarray) -> None:
        if not self._armed:
            return
        try:
            self._queue.put_nowait(chunk)
        except queue.Full:
            pass  # mejor perder audio que bloquear el hilo de audio

    def _work(self) -> None:
        while True:
            chunk = self._queue.get()
            if self._armed:
                self._process(chunk)

    def _process(self, chunk: np.ndarray) -> None:
        pcm = (np.clip(chunk, -1, 1) * 32767).astype("int16").tobytes()
        if self._recognizer.AcceptWaveform(pcm):
            result = self._recognizer.Result()
        else:
            result = self._recognizer.PartialResult()
        if heard_word(result, self.word) and self._now() - self._last_fire >= DEBOUNCE_S:
            self._last_fire = self._now()
            self._recognizer.Reset()
            self.on_detect()
```

- [ ] **Step 5: Verificar que pasan**

Run: `.venv\Scripts\python -m pytest tests/test_wakeword.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add dicta/wakeword.py tests/test_wakeword.py pyproject.toml
git commit -m "feat: wake word con Vosk en modo gramatica + descarga del modelo"
```

---

### Task 8: Widget — "Ecualizador en calma" con cápsula

**Files:**
- Modify: `dicta/widget.py` (reescritura completa)
- Modify: `tests/manual_widget_demo.py`

No hay tests unitarios de pintura; la validación es la demo manual (paso 3). La función `wave_scale` sí se testea.

- [ ] **Step 1: Test de `wave_scale`.** Crear `tests/test_widget_logic.py`:

```python
"""Lógica pura del widget (sin Qt)."""
from dicta.widget import wave_scale


def test_wave_scale_reposo_pico_y_vuelta():
    assert wave_scale(0.0) == 0.4          # arranque en reposo
    assert abs(wave_scale(0.12) - 0.95) < 1e-9  # pico
    assert wave_scale(0.28) == 0.4         # vuelta al reposo
    assert wave_scale(0.6) == 0.4          # resto del ciclo, quieto
    assert abs(wave_scale(1.12) - wave_scale(0.12)) < 1e-9  # periódica (con epsilon: % 1.0 no es exacto)
```

Run: `.venv\Scripts\python -m pytest tests/test_widget_logic.py -v`
Expected: FAIL con `ImportError: cannot import name 'wave_scale'`

- [ ] **Step 2: Reescribir `dicta/widget.py`** completo:

```python
"""Widget flotante "ecualizador en calma": círculo de 52px con 5 barras que
se estira en cápsula de 116px al trabajar. Click = dictar, drag = mover,
click derecho = menú (Manos libres / Salir). Solo pinta estados; la lógica
vive en state.py. La ventana tiene tamaño FIJO (140x72) y la forma pintada
se ancla al borde derecho: así el dock no se mueve al expandirse. Ya no es
always-on-top: el Docker la coloca sobre la terminal en el z-order."""
import math

from PyQt6.QtCore import (
    QEasingCurve, QPoint, QPointF, QRectF, Qt, QVariantAnimation, pyqtSignal,
)
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QMenu, QWidget

from dicta.state import State

CANVAS_W = 140
CANVAS_H = 72
CIRCLE = 52   # diámetro en reposo
PILL_W = 116  # ancho expandido (escuchando/transcribiendo)
AIR = 10      # aire entre la forma y el borde derecho de la ventana

_IVORY = QColor("#F5F4EF")
_CLAY = QColor("#D97757")
_INK = QColor("#262625")
_GRAY = QColor("#A8A49C")
_DARK_RED = QColor("#A12A22")

# Estado -> (fondo, color de contenido, modo de contenido, ancho de la forma)
_STYLES = {
    State.LOADING: (_IVORY, _GRAY, "bars-breath", CIRCLE),
    State.IDLE: (_IVORY, _CLAY, "bars-calm", CIRCLE),
    State.ARMED: (_IVORY, _CLAY, "bars-wave", CIRCLE),
    State.LISTENING: (_CLAY, _IVORY, "bars-live", PILL_W),
    State.TRANSCRIBING: (_INK, _IVORY, "dots", PILL_W),
    State.ERROR: (_DARK_RED, _IVORY, "bang", CIRCLE),
}

_LOOP_MS = {"bars-breath": 2400, "bars-wave": 3200, "dots": 1200}

_TIPS = {
    State.LOADING: "dicta — cargando modelo…",
    State.IDLE: "dicta — click para dictar",
    State.ARMED: 'dicta — di "Claude" o haz click para dictar',
    State.LISTENING: "Escuchando… click para terminar",
    State.TRANSCRIBING: "Transcribiendo…",
    State.ERROR: "Error — click para reintentar (mira la consola)",
}

BAR_W = 4.0
BAR_GAP = 4.0
CALM_HEIGHTS = (7.0, 12.0, 17.0, 12.0, 7.0)
WAVE_BASE = 20.0
WAVE_DELAYS = (0.0, 0.056, 0.112, 0.168, 0.224)  # ~0.18 s entre barras (ciclo 3.2 s)
LIVE_WEIGHTS = (0.6, 0.85, 1.0, 0.85, 0.6)
LIVE_MAX = 24.0


def wave_scale(t: float) -> float:
    """Pulso de la onda en ARMED: sube a 0.95 en t=0.12, baja a 0.4 en t=0.28."""
    t %= 1.0
    if t < 0.12:
        return 0.4 + 0.55 * (t / 0.12)
    if t < 0.28:
        return 0.95 - 0.55 * ((t - 0.12) / 0.16)
    return 0.4


class DictaWidget(QWidget):
    clicked = pyqtSignal()
    quit_requested = pyqtSignal()
    drag_finished = pyqtSignal()
    handsfree_toggled = pyqtSignal(bool)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(CANVAS_W, CANVAS_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._drag_offset: QPoint | None = None
        self._moved = False
        self._hovered = False
        self._handsfree = False

        self._bg = QColor(_IVORY)
        self._fg = QColor(_GRAY)
        self._mode = "bars-breath"
        self._phase = 0.0
        self._scale = 1.0
        self._shape_w = float(CIRCLE)
        self._level = 0.0

        # Escala (hover/press): interrumpible, siempre desde el valor actual.
        self._scale_anim = QVariantAnimation(self)
        self._scale_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._scale_anim.valueChanged.connect(self._on_scale)

        # Expansión círculo <-> cápsula.
        self._width_anim = QVariantAnimation(self)
        self._width_anim.setDuration(200)
        self._width_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._width_anim.valueChanged.connect(self._on_width)

        # Crossfade de color entre estados.
        self._bg_anim = self._color_anim(self._on_bg)
        self._fg_anim = self._color_anim(self._on_fg)

        # Fase 0→1 en bucle para breath/wave/dots.
        self._loop = QVariantAnimation(self)
        self._loop.setStartValue(0.0)
        self._loop.setEndValue(1.0)
        self._loop.setLoopCount(-1)
        self._loop.setEasingCurve(QEasingCurve.Type.Linear)
        self._loop.valueChanged.connect(self._on_phase)

        self.set_state(State.LOADING)

    # --- estados ---

    def set_state(self, state: State) -> None:
        bg, fg, mode, width = _STYLES[state]
        self._animate_color(self._bg_anim, self._bg, bg)
        self._animate_color(self._fg_anim, self._fg, fg)
        if mode != self._mode:
            self._mode = mode
            self._loop.stop()
            self._phase = 0.0
            if mode in _LOOP_MS:
                self._loop.setDuration(_LOOP_MS[mode])
                self._loop.start()
        if float(width) != self._shape_w:
            self._width_anim.stop()
            self._width_anim.setStartValue(self._shape_w)
            self._width_anim.setEndValue(float(width))
            self._width_anim.start()
        if mode != "bars-live":
            self._level = 0.0
        self.setToolTip(_TIPS[state])
        self.update()

    def set_level(self, level: float) -> None:
        """Nivel RMS 0..~0.3 del micrófono; mueve las barras en LISTENING.
        Ataque rápido, caída suave: el pico empuja, el silencio decae."""
        self._level = max(min(level * 3.0, 1.0), self._level * 0.85)
        if self._mode == "bars-live":
            self.update()

    def set_handsfree(self, enabled: bool) -> None:
        self._handsfree = enabled

    def is_dragging(self) -> bool:
        return self._drag_offset is not None and self._moved

    # --- geometría ---

    def _shape_rect(self) -> QRectF:
        w = self._shape_w * self._scale
        h = CIRCLE * self._scale
        cx = CANVAS_W - AIR - self._shape_w / 2
        cy = CANVAS_H / 2
        return QRectF(cx - w / 2, cy - h / 2, w, h)

    # --- pintura ---

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self._shape_rect()
        radius = rect.height() / 2

        # sombra suave + forma con borde sutil (se ve sobre fondos claros)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 46))
        p.drawRoundedRect(rect.translated(0, 1.5), radius, radius)
        p.setPen(QPen(QColor(0, 0, 0, 30), 1))
        p.setBrush(self._bg)
        p.drawRoundedRect(rect, radius, radius)

        p.setPen(Qt.PenStyle.NoPen)
        center = rect.center()
        if self._mode == "dots":
            self._paint_dots(p, center)
        elif self._mode == "bang":
            self._paint_bang(p, center)
        else:
            self._paint_bars(p, center)

    def _bar_heights(self) -> list[float]:
        if self._mode == "bars-wave":
            return [WAVE_BASE * wave_scale(self._phase - d) for d in WAVE_DELAYS]
        if self._mode == "bars-live":
            return [max(4.0, LIVE_MAX * self._level * w) for w in LIVE_WEIGHTS]
        return list(CALM_HEIGHTS)  # bars-calm y bars-breath

    def _paint_bars(self, p: QPainter, center: QPointF) -> None:
        fg = QColor(self._fg)
        if self._mode == "bars-breath":
            fg.setAlphaF(0.35 + 0.5 * (0.5 - 0.5 * math.cos(self._phase * 2 * math.pi)))
        p.setBrush(fg)
        heights = self._bar_heights()
        s = self._scale
        total = (len(heights) * BAR_W + (len(heights) - 1) * BAR_GAP) * s
        x = center.x() - total / 2
        for h in heights:
            bh, bw = h * s, BAR_W * s
            p.drawRoundedRect(QRectF(x, center.y() - bh / 2, bw, bh), bw / 2, bw / 2)
            x += (BAR_W + BAR_GAP) * s

    def _paint_dots(self, p: QPainter, center: QPointF) -> None:
        s = self._scale
        for i in range(3):
            fg = QColor(self._fg)
            t = (self._phase - i * 0.167) % 1.0
            fg.setAlphaF(0.25 + 0.75 * (0.5 - 0.5 * math.cos(t * 2 * math.pi)))
            p.setBrush(fg)
            p.drawEllipse(QPointF(center.x() + (i - 1) * 12 * s, center.y()), 3 * s, 3 * s)

    def _paint_bang(self, p: QPainter, center: QPointF) -> None:
        s = self._scale
        p.setBrush(QColor(self._fg))
        p.drawRoundedRect(
            QRectF(center.x() - 2.5 * s, center.y() - 12 * s, 5 * s, 16 * s),
            2.5 * s, 2.5 * s,
        )
        p.drawEllipse(QPointF(center.x(), center.y() + 9 * s), 2.5 * s, 2.5 * s)

    # --- animaciones ---

    def _color_anim(self, on_value) -> QVariantAnimation:
        anim = QVariantAnimation(self)
        anim.setDuration(180)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.valueChanged.connect(on_value)
        return anim

    @staticmethod
    def _animate_color(anim: QVariantAnimation, start: QColor, end: QColor) -> None:
        anim.stop()
        anim.setStartValue(QColor(start))
        anim.setEndValue(QColor(end))
        anim.start()

    def _animate_scale(self, target: float, ms: int) -> None:
        self._scale_anim.stop()
        self._scale_anim.setStartValue(self._scale)
        self._scale_anim.setEndValue(target)
        self._scale_anim.setDuration(ms)
        self._scale_anim.start()

    def _on_scale(self, v) -> None:
        self._scale = v
        self.update()

    def _on_width(self, v) -> None:
        self._shape_w = v
        self.update()

    def _on_bg(self, v) -> None:
        self._bg = v
        self.update()

    def _on_fg(self, v) -> None:
        self._fg = v
        self.update()

    def _on_phase(self, v) -> None:
        self._phase = v
        self.update()

    # --- ratón: distinguir click de drag (si se movió más de 3px, es drag) ---

    def enterEvent(self, e) -> None:
        self._hovered = True
        if self._drag_offset is None:
            self._animate_scale(1.06, 140)

    def leaveEvent(self, e) -> None:
        self._hovered = False
        if self._drag_offset is None:
            self._animate_scale(1.0, 140)

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton and self._shape_rect().contains(e.position()):
            self._drag_offset = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._moved = False
            self._animate_scale(0.93, 100)

    def mouseMoveEvent(self, e) -> None:
        if self._drag_offset is not None:
            new_pos = e.globalPosition().toPoint() - self._drag_offset
            # Umbral solo para iniciar el drag; ya iniciado, mover siempre.
            if self._moved or (new_pos - self.pos()).manhattanLength() > 3:
                self._moved = True
                self.move(new_pos)

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton and self._drag_offset is not None:
            moved = self._moved
            self._drag_offset = None
            self._animate_scale(1.06 if self._hovered else 1.0, 160)
            if moved:
                self.drag_finished.emit()
            else:
                self.clicked.emit()

    def contextMenuEvent(self, e) -> None:
        menu = QMenu(self)
        hf = menu.addAction("Manos libres")
        hf.setCheckable(True)
        hf.setChecked(self._handsfree)
        hf.toggled.connect(self.handsfree_toggled.emit)
        menu.addSeparator()
        menu.addAction("Salir", self.quit_requested.emit)
        menu.exec(e.globalPos())
```

Notas: ya no hay `WindowStaysOnTopHint` (el z-order lo gestiona el Docker en Task 9). `mousePressEvent` hace hit-test contra la forma: clicks en el aire de la ventana no cuentan. `mouseReleaseEvent` comprueba `self._drag_offset is not None` para ignorar releases cuyo press cayó fuera de la forma.

- [ ] **Step 3: Verificar el test de lógica**

Run: `.venv\Scripts\python -m pytest tests/test_widget_logic.py -v`
Expected: PASS

- [ ] **Step 4: Actualizar la demo.** En `tests/manual_widget_demo.py`: añadir `import math` junto a los imports, añadir `State.ARMED` a `STATES` (entre `IDLE` y `LISTENING`), y antes de `return app.exec()` del modo cíclico añadir:

```python
    # nivel simulado para ver las barras vivas en LISTENING
    level_timer = QTimer()
    k = 0

    def pump_level() -> None:
        nonlocal k
        k += 1
        widget.set_level(0.05 + 0.15 * (1 + math.sin(k / 2.5)))

    level_timer.timeout.connect(pump_level)
    level_timer.start(33)
```

- [ ] **Step 5: Validación visual manual**

Run: `.venv\Scripts\python tests/manual_widget_demo.py`
Expected: cicla LOADING (barras grises respirando) → IDLE (barras terracota quietas) → ARMED (onda lenta) → LISTENING (cápsula terracota, barras bailando con el nivel simulado) → TRANSCRIBING (cápsula tinta, 3 puntos) → ERROR (círculo rojo con "!"). La forma se expande/colapsa con el borde derecho fijo. Click derecho muestra "Manos libres" y "Salir".

- [ ] **Step 6: Suite completa** (los tests viejos del widget no existen; verificar que nada más se rompió)

Run: `.venv\Scripts\python -m pytest tests/ -v`
Expected: PASS (todos)

- [ ] **Step 7: Commit**

```bash
git add dicta/widget.py tests/test_widget_logic.py tests/manual_widget_demo.py
git commit -m "feat: widget ecualizador en calma con capsula expandible (C1)"
```

---

### Task 9: Docking — el widget vive sobre la terminal (z-order)

**Files:**
- Modify: `dicta/docking.py`
- Test: `tests/test_docking.py`

- [ ] **Step 1: Test que falla.** En `tests/test_docking.py`, añadir el método `winId` a `_FakeWidget`:

```python
    def winId(self):
        return 7
```

Y añadir al final del archivo:

```python
def test_dock_coloca_el_widget_sobre_la_terminal(monkeypatch):
    import dicta.docking as docking

    placed = []
    monkeypatch.setattr(docking, "place_above", lambda w, t: placed.append((w, t)))
    monkeypatch.setattr(docking.win32gui, "IsWindow", lambda h: True)
    monkeypatch.setattr(docking.win32gui, "IsIconic", lambda h: False)
    monkeypatch.setattr(docking.win32gui, "GetWindowRect", lambda h: (0, 0, 800, 600))
    w = _FakeWidget()
    tracker = _FakeTracker()
    tracker.last_terminal_hwnd = 99
    d = Docker(w, tracker)
    d.tick()
    assert placed == [(7, 99)]
```

- [ ] **Step 2: Verificar que falla**

Run: `.venv\Scripts\python -m pytest tests/test_docking.py -v`
Expected: FAIL con `AttributeError: ... 'place_above'`

- [ ] **Step 3: Implementar.** En `dicta/docking.py`: cambiar el import y añadir `place_above`:

```python
import win32con
import win32gui
```

```python
def place_above(widget_hwnd: int, terminal_hwnd: int) -> None:
    """Coloca el widget justo encima de la terminal en el z-order (sin topmost):
    si otra app tapa la terminal, tapa también el widget."""
    prev = win32gui.GetWindow(terminal_hwnd, win32con.GW_HWNDPREV)
    if prev == widget_hwnd:
        return
    flags = win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE
    win32gui.SetWindowPos(widget_hwnd, prev, 0, 0, 0, 0, flags)
```

(`prev == 0` significa que la terminal es la primera: `SetWindowPos` con `hWndInsertAfter=0` = `HWND_TOP`, correcto.)

Y en `Docker.tick()`, al final (después del `self.widget.move(x, y)` condicional):

```python
        try:
            place_above(int(self.widget.winId()), hwnd)
        except Exception:
            pass  # la terminal pudo cerrarse entre medias
```

- [ ] **Step 4: Verificar que pasan (todos los de docking)**

Run: `.venv\Scripts\python -m pytest tests/test_docking.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add dicta/docking.py tests/test_docking.py
git commit -m "fix: el widget vive sobre la terminal en el z-order, no sobre todo"
```

---

### Task 10: app.py — cableado completo

**Files:**
- Modify: `dicta/app.py`

Sin tests unitarios (es cableado Qt + hilos); la validación es arrancar dicta (Step 3) y la checklist manual (Task 11).

- [ ] **Step 1: Reescribir `dicta/app.py`** completo:

```python
"""Orquestador: une widget, estados, bus de audio, wake word, grabadora,
transcriptor e inyector."""
import json
import sys
import threading
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication

from dicta import injector, singleton, sounds
from dicta.audio import AudioBus
from dicta.config import APP_DIR, Config, ensure_config, load_config
from dicta.docking import Docker
from dicta.focus_tracker import FocusTracker
from dicta.recorder import Recorder
from dicta.silence import SilenceDetector
from dicta.state import State, StateMachine
from dicta.widget import DictaWidget

STATE_FILE = APP_DIR / "state.json"
MODELS_DIR = APP_DIR / "models"
EXAMPLE_CONFIG = Path(__file__).parent.parent / "config.example.toml"


class Bridge(QObject):
    """Señales para cruzar de hilos de trabajo al hilo de Qt (thread-safe)."""

    model_ready = pyqtSignal()
    model_failed = pyqtSignal()
    transcription_done = pyqtSignal(str)
    transcription_failed = pyqtSignal()
    injection_finished = pyqtSignal(bool)
    hotkey_pressed = pyqtSignal()
    wake_detected = pyqtSignal()
    wake_ready = pyqtSignal()
    wake_failed = pyqtSignal()
    silence_event = pyqtSignal(str)  # "silence" | "timeout"
    mic_level = pyqtSignal(float)


def load_ui_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {}


def save_ui_state(widget, docker: Docker) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(
            {
                "x": widget.x(),
                "y": widget.y(),
                "dx": docker.offset[0],
                "dy": docker.offset[1],
            }
        )
    )


def main() -> int:
    if singleton.already_running():
        print("dicta ya está corriendo.")
        return 0
    singleton.write_pid()
    if EXAMPLE_CONFIG.exists():
        ensure_config(EXAMPLE_CONFIG)
    cfg: Config = load_config()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    sm = StateMachine(handsfree_enabled=cfg.manos_libres_activado)
    widget = DictaWidget()
    bus = AudioBus()
    recorder = Recorder(bus)
    bridge = Bridge()
    holder: dict = {}           # {"t": Transcriber} cuando cargue
    detector_holder: dict = {}  # {"d": WakeWordDetector} cuando cargue
    silence_holder: dict = {}   # {"s": SilenceDetector, "cb": callback} por sesión

    # Posición inicial: persistida, o esquina inferior derecha por defecto.
    ui_state = load_ui_state()
    if "x" in ui_state and "y" in ui_state:
        widget.move(int(ui_state["x"]), int(ui_state["y"]))
    else:
        geo = app.primaryScreen().availableGeometry()
        widget.move(geo.right() - widget.width() - 16, geo.bottom() - widget.height() - 16)
    widget.show()

    tracker = FocusTracker(int(widget.winId()))
    poll_timer = QTimer()
    poll_timer.timeout.connect(tracker.poll)
    poll_timer.start(500)

    docker = Docker(
        widget, tracker, (int(ui_state.get("dx", 0)), int(ui_state.get("dy", 0)))
    )
    dock_timer = QTimer()
    dock_timer.timeout.connect(docker.tick)
    dock_timer.start(80)
    widget.drag_finished.connect(docker.recompute_offset)

    # --- cableado de estados y UI ---
    sm.on_change.append(widget.set_state)
    widget.clicked.connect(sm.click)
    widget.quit_requested.connect(app.quit)
    bridge.model_ready.connect(sm.model_ready)
    bridge.model_failed.connect(sm.fail)
    bridge.hotkey_pressed.connect(sm.click)
    bridge.wake_detected.connect(sm.wake_detected)
    bridge.mic_level.connect(widget.set_level)

    # --- nivel del micrófono -> barras (solo mientras se escucha) ---
    level_counter = {"n": 0}

    def on_chunk_level(chunk: np.ndarray) -> None:
        level_counter["n"] += 1
        if level_counter["n"] % 3 == 0:  # ~30 fps con chunks de ~10 ms
            bridge.mic_level.emit(float(np.sqrt(np.mean(chunk**2))))

    # --- grabación ---
    def start_recording() -> None:
        if "t" not in holder:
            print("El modelo no está cargado; no se puede dictar.", file=sys.stderr)
            sounds.play("error", cfg.sonidos)
            sm.fail()
            return
        sounds.play("start", cfg.sonidos)
        try:
            recorder.start()
            bus.subscribe(on_chunk_level)
        except Exception as exc:
            print(f"Error de micrófono: {exc}", file=sys.stderr)
            sounds.play("error", cfg.sonidos)
            sm.fail()
            return
        if sm.session_handsfree:
            det = SilenceDetector(cfg.silencio_segundos)
            silence_holder["s"] = det

            def feed_silence(chunk: np.ndarray, _det=det) -> None:
                event = _det.feed(chunk)
                if event:
                    bridge.silence_event.emit(event)

            silence_holder["cb"] = feed_silence
            bus.subscribe(feed_silence)

    def cleanup_listening() -> None:
        bus.unsubscribe(on_chunk_level)
        cb = silence_holder.pop("cb", None)
        if cb is not None:
            bus.unsubscribe(cb)
        silence_holder.pop("s", None)

    def stop_and_transcribe() -> None:
        sounds.play("stop", cfg.sonidos)
        cleanup_listening()
        audio_data = recorder.stop()

        def work() -> None:
            try:
                text = holder["t"].transcribe(audio_data)
                bridge.transcription_done.emit(text)
            except Exception as exc:
                print(f"Error transcribiendo: {exc}", file=sys.stderr)
                bridge.transcription_failed.emit()

        threading.Thread(target=work, daemon=True).start()

    def cancel_listening() -> None:
        cleanup_listening()
        recorder.discard()
        sounds.play("error", cfg.sonidos)

    sm.on_start_listening.append(start_recording)
    sm.on_stop_listening.append(stop_and_transcribe)
    sm.on_cancel_listening.append(cancel_listening)

    def on_silence_event(event: str) -> None:
        if event == "silence":
            sm.silence_detected()
        else:  # "timeout": nunca hubo voz
            sm.cancel()

    bridge.silence_event.connect(on_silence_event)

    # --- resultado de la transcripción ---
    def on_done(text: str) -> None:
        if not text:
            sounds.play("error", cfg.sonidos)  # silencio/ruido: no pegar nada
            sm.transcription_done()
            return
        # En manos libres el destino es SIEMPRE la terminal (un Enter automático
        # en otra app sería peligroso); en manual, la última ventana activa.
        handsfree = sm.session_handsfree
        target = tracker.last_terminal_hwnd if handsfree else tracker.last_hwnd
        send_enter = handsfree and cfg.auto_enviar
        threading.Thread(
            target=lambda: bridge.injection_finished.emit(
                injector.inject(text, target, cfg.paste_shortcut, send_enter)
            ),
            daemon=True,
        ).start()

    def on_injection_finished(ok: bool) -> None:
        if not ok:
            sounds.play("error", cfg.sonidos)  # quedó en el clipboard
            print("No se pudo pegar; la transcripción está en el clipboard.")
        sm.transcription_done()

    bridge.transcription_done.connect(on_done)
    bridge.injection_finished.connect(on_injection_finished)
    bridge.transcription_failed.connect(
        lambda: (sounds.play("error", cfg.sonidos), sm.fail())
    )

    # --- wake word ---
    def load_wakeword() -> None:
        try:
            from dicta.wakeword import WakeWordDetector, ensure_model

            model_dir = ensure_model(MODELS_DIR)
            detector_holder["d"] = WakeWordDetector(
                model_dir, cfg.wake_word, bridge.wake_detected.emit
            )
            bridge.wake_ready.emit()
        except Exception as exc:
            print(f"Wake word no disponible: {exc}", file=sys.stderr)
            bridge.wake_failed.emit()

    def sync_detector(state: State) -> None:
        """El detector solo procesa en ARMED; suscrito salvo en reposo apagado."""
        det = detector_holder.get("d")
        if det is None:
            return
        det.set_armed(state is State.ARMED)
        if state is State.ARMED:
            try:
                bus.subscribe(det.feed)
            except Exception as exc:
                print(f"Error de micrófono: {exc}", file=sys.stderr)
                sm.fail()
        elif state in (State.IDLE, State.ERROR):
            bus.unsubscribe(det.feed)

    sm.on_change.append(sync_detector)
    bridge.wake_ready.connect(lambda: sync_detector(sm.state))

    def on_wake_failed() -> None:
        if sm.handsfree_enabled:
            sm.toggle_handsfree()  # manos libres OFF; el flujo manual sigue
        widget.set_handsfree(False)

    bridge.wake_failed.connect(on_wake_failed)

    def on_handsfree_toggled(enabled: bool) -> None:
        if enabled and "d" not in detector_holder:
            threading.Thread(target=load_wakeword, daemon=True).start()
        if enabled != sm.handsfree_enabled:
            sm.toggle_handsfree()
        widget.set_handsfree(enabled)

    widget.handsfree_toggled.connect(on_handsfree_toggled)
    widget.set_handsfree(cfg.manos_libres_activado)
    if cfg.manos_libres_activado:
        threading.Thread(target=load_wakeword, daemon=True).start()

    # --- carga del modelo en background ---
    def load_model() -> None:
        try:
            from dicta.transcriber import Transcriber

            print(f"Cargando modelo {cfg.model}… (la primera vez descarga ~3 GB)")
            holder["t"] = Transcriber(cfg.model, cfg.language, cfg.vocabulario)
            print(f"Modelo listo en {holder['t'].device}.")
            bridge.model_ready.emit()
        except Exception as exc:
            print(f"No se pudo cargar el modelo: {exc}", file=sys.stderr)
            bridge.model_failed.emit()

    threading.Thread(target=load_model, daemon=True).start()

    # --- hotkey opcional ---
    if cfg.hotkey_enabled:
        import keyboard

        keyboard.add_hotkey(cfg.hotkey_combo, bridge.hotkey_pressed.emit)

    # --- auto-cierre cuando los hooks indican 0 sesiones de Claude Code ---
    exit_timer = QTimer()
    exit_timer.timeout.connect(
        lambda: app.quit() if singleton.should_exit(singleton.read_counter()) else None
    )
    exit_timer.start(2000)

    app.aboutToQuit.connect(lambda: save_ui_state(widget, docker))
    return app.exec()
```

- [ ] **Step 2: Suite completa**

Run: `.venv\Scripts\python -m pytest tests/ -v`
Expected: PASS (todos)

- [ ] **Step 3: Humo manual rápido**

Run: `.venv\Scripts\python -m dicta`
Expected: arranca; consola muestra la descarga del modelo Vosk la primera vez ("Descargando modelo de wake word…") y "Cargando modelo large-v3…"; el widget pasa de barras grises a la onda lenta (ARMED) cuando ambos modelos cargan. Decir "Claude" → ding → cápsula. Cerrar con click derecho → Salir.

- [ ] **Step 4: Commit**

```bash
git add dicta/app.py
git commit -m "feat: cableado manos libres (wake word, silencio, envio directo)"
```

---

### Task 11: Config de ejemplo, docs y cierre

**Files:**
- Modify: `config.example.toml`
- Modify: `docs/manual-test-checklist.md`
- Modify: `README.md`

- [ ] **Step 1: `config.example.toml`** — añadir al final:

```toml

[manos_libres]
activado = true
palabra = "claude"
silencio_segundos = 2.0
auto_enviar = true
```

- [ ] **Step 2: Checklist manual.** En `docs/manual-test-checklist.md`, añadir antes de la sección `## Hooks`:

```markdown
## Manos libres (wake word)
- [ ] Primera vez: consola muestra la descarga del modelo Vosk (~39 MB)
- [ ] Widget en onda lenta (armado) → decir "Claude" → ding → cápsula escuchando
- [ ] Las barras de la cápsula se mueven al hablar y caen al callar
- [ ] Hablar y callar ~2 s → transcribe → el texto aparece en la terminal Y SE ENVÍA (Enter)
- [ ] Dictado por click (no wake word) → el texto NO se envía (sin Enter)
- [ ] Decir "Claude" y no hablar → a los ~10 s beep suave y vuelve a armado (no pega nada)
- [ ] Decir "Claude" durante un dictado en curso → no hace nada
- [ ] Click derecho → desmarcar "Manos libres" → barras quietas (reposo); decir "Claude" no hace nada
- [ ] Volver a marcar "Manos libres" → onda lenta, vuelve a responder
- [ ] Falso positivo: mantener una conversación cerca del micro 1 min sin decir "Claude" → no se dispara

## Z-order (fix botón pegado)
- [ ] Con la terminal delante: el botón se ve pegado a su esquina
- [ ] Tapar la terminal con otra ventana (sin minimizar) → el botón queda DETRÁS (no flota encima)
- [ ] Traer la terminal al frente → el botón emerge con ella
- [ ] Minimizar la terminal → el botón se oculta; restaurar → reaparece
```

Y actualizar las líneas obsoletas de la sección Widget/Arranque que mencionan los glifos viejos: donde dice `gris (cargando) → azul 📞 (listo)` dejar `barras grises respirando (cargando) → onda lenta terracota (armado) o barras quietas (reposo)`; donde dice `widget rojo 🎙` dejar `cápsula terracota con barras`; donde dice `widget naranja ✍` dejar `cápsula tinta con puntos`; donde dice `widget en error ⚠` dejar `widget en error (círculo rojo con !)`. Actualizar también el título a `RTX 5070`.

- [ ] **Step 3: README.** En `README.md`, añadir una sección breve después de la descripción general (adaptar al estilo del archivo al editarlo):

```markdown
## Manos libres ("Claude")

Con `[manos_libres] activado = true` (default), dicta escucha en local la palabra
**"Claude"** (Vosk, modelo pequeño en español, sin nube ni cuentas). Di "Claude",
habla, y al callarte ~2 s dicta transcribe, pega el texto en la terminal y lo envía
con Enter automático (`auto_enviar = false` para desactivar el Enter). El dictado
por click sigue igual: pega sin enviar, tú revisas. Click derecho en el botón →
"Manos libres" para apagarlo/encenderlo al vuelo. Riesgo conocido: hablar mucho
cerca del micro puede disparar falsos positivos; apágalo en llamadas si molesta.
```

- [ ] **Step 4: Suite completa final**

Run: `.venv\Scripts\python -m pytest tests/ -v`
Expected: PASS (todos)

- [ ] **Step 5: Commit**

```bash
git add config.example.toml docs/manual-test-checklist.md README.md
git commit -m "docs: config de ejemplo y checklist manual para manos libres"
```

- [ ] **Step 6: Cierre.** Recordar a Robert: queda la checklist manual (micrófono real) y el push requiere su OK explícito.

---

## Notas para el ejecutor

- **Entorno:** Windows 11, venv en `X:\Proyectos\dicta\.venv`. pywin32, PyQt6 y sounddevice ya instalados. Los tests NO necesitan micrófono, GPU ni modelos: todo lo de hardware está mockeado/inyectado.
- **No tocar:** `singleton.py`, `transcriber.py`, `focus_tracker.py`, `sounds.py`, los hooks — quedan como están.
- **dicta corriendo:** si dicta está abierto durante el desarrollo, cerrarlo antes de probar (`click derecho → Salir`); el singleton impide segundas instancias.
- **Posición guardada:** `%APPDATA%\dicta\state.json` guarda la posición de la ventana vieja (72px); con la nueva (140px) el offset visual cambia unos píxeles la primera vez — se recoloca solo al detectar la terminal. No requiere migración.
