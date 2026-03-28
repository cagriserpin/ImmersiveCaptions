from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget


class CaptionOverlay(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setStyleSheet("background: transparent;")