"""Máquina de estados pura (sin Qt). El widget pinta según on_change;
la app arranca/para la grabadora según on_start/stop/cancel_listening,
y controla la voz de salida según speak_request/speak_done.
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
    SPEAKING = auto()
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
        self.speak_abre_mic = False
        self.on_stop_speaking: list[Callable[[], None]] = []

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
        """Solo válido desde LOADING (se llama una vez al arrancar)."""
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
        elif self.state is State.SPEAKING:
            self._dispatch(self.on_stop_speaking)
            self.session_handsfree = True
            self._set(State.LISTENING)
            self._dispatch(self.on_start_listening)
        elif self.state is State.ERROR:
            self._set(self._resting())
        # LOADING y TRANSCRIBING ignoran clicks

    def wake_detected(self) -> None:
        if self.state is State.ARMED:
            self.session_handsfree = True
            self._set(State.LISTENING)
            self._dispatch(self.on_start_listening)

    def speak_request(self, abre_mic: bool) -> bool:
        """True si dicta pasa a hablar YA; False = el llamante lo deja en cola.
        Solo se habla desde reposo: un dictado en curso nunca se interrumpe."""
        if self.state in (State.IDLE, State.ARMED):
            self.speak_abre_mic = abre_mic
            self._set(State.SPEAKING)
            return True
        return False

    def speak_done(self) -> None:
        """Fin de la reproducción. Con abre_mic la conversación sigue sola."""
        if self.state is not State.SPEAKING:
            return  # p. ej. un click ya cortó y abrió escucha
        if self.speak_abre_mic:
            self.session_handsfree = True
            self._set(State.LISTENING)
            self._dispatch(self.on_start_listening)
        else:
            self._set(self._resting())

    def silence_detected(self) -> None:
        if self.state is State.LISTENING and self.session_handsfree:
            self._set(State.TRANSCRIBING)
            self._dispatch(self.on_stop_listening)

    def cancel(self) -> None:
        """Aborta el dictado sin transcribir (timeout sin voz, solo manos libres)."""
        if self.state is State.LISTENING and self.session_handsfree:
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
            self.session_handsfree = False
            self._set(State.ERROR)
