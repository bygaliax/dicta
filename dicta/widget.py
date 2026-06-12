"""Widget flotante: botón circular always-on-top con el spark estilo Anthropic.
Click = dictar, drag = mover, click derecho = menú Salir. Animaciones por estado:
ripple al escuchar, rotación al transcribir, respiración al cargar; hover y press
con escala. Solo pinta estados; la lógica vive en state.py."""
import math

from PyQt6.QtCore import QEasingCurve, QPoint, QPointF, Qt, QVariantAnimation, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import QMenu, QWidget

from dicta.state import State

CANVAS = 72  # tamaño de la ventana; el aire alrededor del botón es para el ripple
BUTTON = 52  # diámetro del botón

_IVORY = QColor("#F5F4EF")  # marfil Anthropic
_CLAY = QColor("#D97757")   # terracota Claude
_INK = QColor("#262625")    # tinta
_GRAY = QColor("#A8A49C")
_DARK_RED = QColor("#A12A22")

# Estado -> (fondo, color del spark, animación: None | pulse | spin | breath)
_STYLES = {
    State.LOADING: (_IVORY, _GRAY, "breath"),
    State.IDLE: (_IVORY, _CLAY, None),
    State.LISTENING: (_CLAY, _IVORY, "pulse"),
    State.TRANSCRIBING: (_INK, _IVORY, "spin"),
    State.ERROR: (_DARK_RED, _IVORY, None),
}

_LOOP_MS = {"pulse": 1100, "spin": 900, "breath": 1600}

_TIPS = {
    State.LOADING: "dicta — cargando modelo…",
    State.IDLE: "dicta — click para dictar",
    State.LISTENING: "Escuchando… click para terminar",
    State.TRANSCRIBING: "Transcribiendo…",
    State.ERROR: "Error — click para reintentar (mira la consola)",
}

# Rayos del spark (ángulo en grados, largo 0..1): asterisco irregular tipo Claude.
_RAYS = [
    (0, 0.95), (42, 0.72), (78, 0.98), (118, 0.70), (152, 0.92),
    (195, 0.75), (228, 0.96), (262, 0.68), (300, 0.90), (338, 0.66),
]


def _spark_path(radius: float) -> QPainterPath:
    """Asterisco de rayos en cometa: nacen en el centro, anchos al 35%, punta fina."""
    path = QPainterPath()
    for deg, frac in _RAYS:
        a = math.radians(deg)
        length = radius * frac
        half_w = length * 0.17
        mid = length * 0.38
        ux, uy = math.cos(a), math.sin(a)         # dirección del rayo
        px, py = -uy, ux                          # perpendicular
        path.addPolygon(QPolygonF([
            QPointF(0, 0),
            QPointF(ux * mid + px * half_w, uy * mid + py * half_w),
            QPointF(ux * length, uy * length),
            QPointF(ux * mid - px * half_w, uy * mid - py * half_w),
        ]))
    return path


class DictaWidget(QWidget):
    clicked = pyqtSignal()
    quit_requested = pyqtSignal()
    drag_finished = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(CANVAS, CANVAS)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._drag_offset: QPoint | None = None
        self._moved = False
        self._hovered = False

        self._spark = _spark_path(BUTTON * 0.31)
        self._bg = QColor(_IVORY)
        self._fg = QColor(_GRAY)
        self._mode: str | None = None
        self._phase = 0.0
        self._scale = 1.0

        # Escala (hover/press): interrumpible, siempre desde el valor actual.
        self._scale_anim = QVariantAnimation(self)
        self._scale_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._scale_anim.valueChanged.connect(self._on_scale)

        # Crossfade de color entre estados.
        self._bg_anim = self._color_anim(self._on_bg)
        self._fg_anim = self._color_anim(self._on_fg)

        # Fase 0→1 en bucle para pulse/spin/breath.
        self._loop = QVariantAnimation(self)
        self._loop.setStartValue(0.0)
        self._loop.setEndValue(1.0)
        self._loop.setLoopCount(-1)
        self._loop.setEasingCurve(QEasingCurve.Type.Linear)
        self._loop.valueChanged.connect(self._on_phase)

        self.set_state(State.LOADING)

    # --- estados ---

    def set_state(self, state: State) -> None:
        bg, fg, mode = _STYLES[state]
        self._animate_color(self._bg_anim, self._bg, bg)
        self._animate_color(self._fg_anim, self._fg, fg)
        if mode != self._mode:
            self._mode = mode
            self._loop.stop()
            self._phase = 0.0
            if mode:
                self._loop.setDuration(_LOOP_MS[mode])
                self._loop.start()
        self.setToolTip(_TIPS[state])
        self.update()

    def is_dragging(self) -> bool:
        return self._drag_offset is not None and self._moved

    # --- pintura ---

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = QPointF(CANVAS / 2, CANVAS / 2)
        r = BUTTON / 2 * self._scale
        if self._mode == "pulse":  # respiración sutil del botón
            r *= 1 + 0.02 * math.sin(self._phase * 2 * math.pi)

        # ripple expandiéndose desde el borde del botón
        if self._mode == "pulse":
            t = 1 - (1 - self._phase) ** 2  # ease-out
            ring_r = r + t * (CANVAS / 2 - r - 1)
            ring = QColor(self._bg)
            ring.setAlphaF(0.45 * (1 - self._phase))
            p.setPen(QPen(ring, 2.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(center, ring_r, ring_r)

        # sombra suave + botón con borde sutil (se ve sobre fondos claros)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 46))
        p.drawEllipse(QPointF(center.x(), center.y() + 1.5), r, r)
        p.setPen(QPen(QColor(0, 0, 0, 30), 1))
        p.setBrush(self._bg)
        p.drawEllipse(center, r, r)

        # spark
        fg = QColor(self._fg)
        if self._mode == "breath":
            fg.setAlphaF(0.35 + 0.5 * (0.5 - 0.5 * math.cos(self._phase * 2 * math.pi)))
        p.save()
        p.translate(center)
        if self._mode == "spin":
            p.rotate(self._phase * 360)
        p.scale(self._scale, self._scale)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(fg)
        p.drawPath(self._spark)
        p.restore()

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
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._moved = False
            self._animate_scale(0.93, 100)

    def mouseMoveEvent(self, e) -> None:
        if self._drag_offset is not None:
            new_pos = e.globalPosition().toPoint() - self._drag_offset
            # Umbral solo para iniciar el drag; ya iniciado, mover siempre (drags lentos suaves).
            if self._moved or (new_pos - self.pos()).manhattanLength() > 3:
                self._moved = True
                self.move(new_pos)

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            moved = self._moved
            self._drag_offset = None
            self._animate_scale(1.06 if self._hovered else 1.0, 160)
            if moved:
                self.drag_finished.emit()
            else:
                self.clicked.emit()

    def contextMenuEvent(self, e) -> None:
        menu = QMenu(self)
        menu.addAction("Salir", self.quit_requested.emit)
        menu.exec(e.globalPos())
