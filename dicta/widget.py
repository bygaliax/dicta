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
        Ataque rápido, caída suave: el pico empuja, el silencio decae.
        En silencio las barras caen a las alturas de CALM (7/12/17/12/7)."""
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
            return [max(ch, LIVE_MAX * self._level * w) for ch, w in zip(CALM_HEIGHTS, LIVE_WEIGHTS)]
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
