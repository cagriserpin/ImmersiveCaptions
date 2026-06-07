import sys

from PySide6.QtWidgets import QApplication
from player_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setOrganizationName("OpenAI")
    app.setApplicationName("ImmersiveCaptions2")

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
