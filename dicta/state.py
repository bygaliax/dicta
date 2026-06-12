"""Máquina de estados pura (sin Qt). El widget pinta según on_change;
la app arranca/para la grabadora según on_start/stop_listening."""
import sys
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
        self._dispatch(self.on_change, state)

    @staticmethod
    def _dispatch(callbacks: list, *args) -> None:
        """Un callback que falla no debe impedir los siguientes."""
        for cb in callbacks:
            try:
                cb(*args)
            except Exception as exc:
                print(f"Error en callback de estado: {exc}", file=sys.stderr)

    def model_ready(self) -> None:
        if self.state is State.LOADING:
            self._set(State.IDLE)

    def click(self) -> None:
        if self.state is State.IDLE:
            self._set(State.LISTENING)
            self._dispatch(self.on_start_listening)
        elif self.state is State.LISTENING:
            self._set(State.TRANSCRIBING)
            self._dispatch(self.on_stop_listening)
        elif self.state is State.ERROR:
            self._set(State.IDLE)
        # LOADING y TRANSCRIBING ignoran clicks

    def transcription_done(self) -> None:
        if self.state is State.TRANSCRIBING:
            self._set(State.IDLE)

    def fail(self) -> None:
        if self.state is not State.ERROR:
            self._set(State.ERROR)
