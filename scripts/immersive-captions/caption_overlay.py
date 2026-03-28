from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QWidget


def to_qfont_weight(weight_value):
    if weight_value <= 150:
        return QFont.Weight.Thin
    if weight_value <= 250:
        return QFont.Weight.ExtraLight
    if weight_value <= 350:
        return QFont.Weight.Light
    if weight_value <= 450:
        return QFont.Weight.Normal
    if weight_value <= 550:
        return QFont.Weight.Medium
    if weight_value <= 650:
        return QFont.Weight.DemiBold
    if weight_value <= 750:
        return QFont.Weight.Bold
    if weight_value <= 850:
        return QFont.Weight.ExtraBold
    return QFont.Weight.Black


class CaptionOverlay(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.caption_model = None
        self.current_time_seconds = 0.0

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setStyleSheet("background-color: rgba(255, 0, 0, 40);")

    def set_caption_model(self, caption_model) -> None:
        self.caption_model = caption_model
        self.update()

    def set_current_time_seconds(self, time_seconds: float) -> None:
        self.current_time_seconds = time_seconds
        self.update()

    def paintEvent(self, event) -> None:
        if self.caption_model is None:
            return

        active_sections = self.caption_model.get_active_sections(self.current_time_seconds)
        if not active_sections:
            return

        defaults = self.caption_model.get_defaults()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        font_name = defaults.get("font", "Arial")
        font_size = defaults.get("font_size", 42)
        font_weight = defaults.get("font_weight", 400)
        font_color = defaults.get("font_color", "#ffffff")

        font = QFont(font_name)
        font.setPointSize(int(font_size))
        font.setWeight(to_qfont_weight(int(font_weight)))

        painter.setFont(font)
        painter.setPen(QColor(font_color))

        section_texts = []
        for section in active_sections:
            text = self.caption_model.section_to_display_text(section)
            if text:
                section_texts.append(text)

        if not section_texts:
            return

        line_height = int(font_size) + 12
        bottom_margin = 60
        total_height = len(section_texts) * line_height
        start_y = self.height() - bottom_margin - total_height

        for index, text in enumerate(section_texts):
            y = start_y + (index * line_height)
            painter.drawText(
                40,
                y,
                self.width() - 80,
                line_height,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                text,
            )

        painter.end()