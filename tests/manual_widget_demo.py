"""Demo visual del widget SIN cargar el modelo (no toca la instancia real de dicta).

Uso:
    python tests/manual_widget_demo.py            # cicla estados cada 2s
    python tests/manual_widget_demo.py --shots X  # guarda PNGs por estado en X y sale
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from dicta.state import State  # noqa: E402
from dicta.widget import DictaWidget  # noqa: E402

STATES = [State.LOADING, State.IDLE, State.ARMED, State.LISTENING, State.TRANSCRIBING, State.ERROR]


def main() -> int:
    app = QApplication(sys.argv)
    widget = DictaWidget()
    widget.move(600, 400)
    widget.show()

    if "--shots" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--shots") + 1])
        out.mkdir(parents=True, exist_ok=True)
        queue = list(STATES)

        def shoot() -> None:
            if not queue:
                app.quit()
                return
            state = queue.pop(0)
            widget.set_state(state)
            # 450ms: deja terminar el crossfade y pilla el loop a media fase
            QTimer.singleShot(450, lambda: capture(state))

        def capture(state: State) -> None:
            widget.grab().save(str(out / f"{state.name.lower()}.png"))
            shoot()

        shoot()
        return app.exec()

    idx = 0

    def cycle() -> None:
        nonlocal idx
        widget.set_state(STATES[idx % len(STATES)])
        print(f"Estado: {STATES[idx % len(STATES)].name}")
        idx += 1

    cycle()
    timer = QTimer()
    timer.timeout.connect(cycle)
    timer.start(2000)
    widget.clicked.connect(lambda: print("click"))
    widget.quit_requested.connect(app.quit)

    # nivel simulado para ver las barras vivas en LISTENING
    level_timer = QTimer()
    k = 0

    def pump_level() -> None:
        nonlocal k
        k += 1
        widget.set_level(0.05 + 0.15 * (1 + math.sin(k / 2.5)))

    level_timer.timeout.connect(pump_level)
    level_timer.start(33)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
