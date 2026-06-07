import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from player_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)

    project_root = Path(__file__).resolve().parents[2]
    default_video_path = project_root / "media" / "video" / "video.mp4"

    window = MainWindow()

    if default_video_path.exists():
        window.load_video(str(default_video_path))

    window.resize(1280, 820)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
