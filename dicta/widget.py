"""Widget flotante: círculo de 56px always-on-top. Click = dictar, drag = mover,
click derecho = menú Salir. Solo pinta estados; la lógica vive en state.py."""
from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtWidgets import QLabel, QMenu, QVBoxLayout, QWidget

from dicta.state import State

_ICONS = {
    State.LOADING: ("⏳", "#666666"),
    State.IDLE: ("📞", "#2563eb"),
    State.LISTENING: ("🎙", "#dc2626"),
    State.TRANSCRIBING: ("✍", "#d97706"),
    State.ERROR: ("⚠", "#7f1d1d"),
}

_TIPS = {
    State.LOADING: "dicta — cargando modelo…",
    State.IDLE: "dicta — click para dictar",
    State.LISTENING: "Escuchando… click para terminar",
    State.TRANSCRIBING: "Transcribiendo…",
    State.ERROR: "Error — click para reintentar (mira la consola)",
}


class DictaWidget(QWidget):
    clicked = pyqtSignal()
    quit_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(56, 56)
        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout = QVBoxLayout(self)
        layout.addWidget(self._label)
        layout.setContentsMargins(0, 0, 0, 0)
        self._drag_offset: QPoint | None = None
        self._moved = False
        self.set_state(State.LOADING)

    def set_state(self, state: State) -> None:
        icon, color = _ICONS[state]
        self._label.setText(icon)
        self._label.setStyleSheet(
            f"background:{color}; color:white; border-radius:28px; font-size:22px;"
        )
        self.setToolTip(_TIPS[state])

    # Distinguir click de drag: si se movió más de 3px, es drag.
    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._moved = False

    def mouseMoveEvent(self, e) -> None:
        if self._drag_offset is not None:
            new_pos = e.globalPosition().toPoint() - self._drag_offset
            # Umbral solo para iniciar el drag; ya iniciado, mover siempre (drags lentos suaves).
            if self._moved or (new_pos - self.pos()).manhattanLength() > 3:
                self._moved = True
                self.move(new_pos)

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            if not self._moved:
                self.clicked.emit()
            self._drag_offset = None

    def contextMenuEvent(self, e) -> None:
        menu = QMenu(self)
        menu.addAction("Salir", self.quit_requested.emit)
        menu.exec(e.globalPos())
