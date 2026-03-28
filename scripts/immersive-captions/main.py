import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from player_window import PlayerWindow


def main() -> int:
    app = QApplication(sys.argv)

    # Adjust this relative path if needed.
    # Assuming this file is inside: scripts/immersive-captions/
    project_root = Path(__file__).resolve().parents[2]
    video_path = project_root / "media" / "video" / "video.mp4"

    window = PlayerWindow(video_path)
    window.resize(1200, 800)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())