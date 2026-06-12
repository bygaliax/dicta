"""Máquina de estados pura (sin Qt). El widget pinta según on_change;
la app arranca/para la grabadora según on_start/stop_listening."""
from enum import Enum, auto
from typing import Callable


class State(Enum):
    LOADING = auto()
    IDLE = auto()
    LISTENING = auto()
    TRANSCRIBING = auto()
    ERROR = auto()


class StateMachine:
    def __init__(self) -> None:
        self.state = State.LOADING
        self.on_change: list[Callable[[State], None]] = []
        self.on_start_listening: list[Callable[[], None]] = []
        self.on_stop_listening: list[Callable[[], None]] = []

    def _set(self, state: State) -> None:
        self.state = state
        for cb in self.on_change:
            cb(state)

    def model_ready(self) -> None:
        if self.state is State.LOADING:
            self._set(State.IDLE)

    def click(self) -> None:
        if self.state is State.IDLE:
            self._set(State.LISTENING)
            for cb in self.on_start_listening:
                cb()
        elif self.state is State.LISTENING:
            self._set(State.TRANSCRIBING)
            for cb in self.on_stop_listening:
                cb()
        elif self.state is State.ERROR:
            self._set(State.IDLE)
        # LOADING y TRANSCRIBING ignoran clicks

    def transcription_done(self) -> None:
        if self.state is State.TRANSCRIBING:
            self._set(State.IDLE)

    def fail(self) -> None:
        self._set(State.ERROR)
