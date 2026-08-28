from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from arp_simulator.ui.main_window import MainWindow


def main() -> int:
    app = QApplication([])
    window = MainWindow()
    window.resize(1600, 1000)
    window.show()

    output = Path(".report_build/ui-main.png").resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    QTimer.singleShot(150, window._start)
    QTimer.singleShot(300, window._resolve)

    def capture() -> None:
        window.grab().save(str(output), "PNG")
        window.close()
        app.quit()

    QTimer.singleShot(2200, capture)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
