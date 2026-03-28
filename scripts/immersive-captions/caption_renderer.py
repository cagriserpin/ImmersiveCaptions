from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QBrush, QColor, QFont, QPen
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsTextItem


def to_qfont_weight(weight_value: int):
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


class CaptionRenderer:
    def __init__(self, scene, caption_model) -> None:
        self.scene = scene
        self.caption_model = caption_model
        self.caption_background_items = []
        self.caption_text_items = []

    def clear(self) -> None:
        for item in self.caption_background_items:
            self.scene.removeItem(item)
        for item in self.caption_text_items:
            self.scene.removeItem(item)

        self.caption_background_items.clear()
        self.caption_text_items.clear()

    def render(self, time_seconds: float) -> None:
        self.clear()

        if self.caption_model is None:
            return

        active_sections = self.caption_model.get_active_sections(time_seconds)
        if not active_sections:
            return

        defaults = self.caption_model.get_defaults()
        speakers = self.caption_model.get_speakers()

        font_name = defaults.get("font", "Arial")
        font_size = int(defaults.get("font_size", 42))
        font_weight = int(defaults.get("font_weight", 400))
        default_color = defaults.get("font_color", "#ffffff")

        view_width = self.scene.sceneRect().width()
        view_height = self.scene.sceneRect().height()

        section_gap = 0
        padding_x = 18
        padding_y = 10
        bottom_margin = 110

        prepared_lines = []

        for section in active_sections:
            text = self.caption_model.section_to_display_text(section)
            if not text:
                continue

            text_color = default_color
            if section.get("type") == "dialogue":
                speaker_name = section.get("speaker")
                if speaker_name in speakers:
                    text_color = speakers[speaker_name].get("font_color", default_color)

            text_item = QGraphicsTextItem()
            text_item.setPlainText(text)

            font = QFont(font_name)
            font.setPointSize(font_size)
            font.setWeight(to_qfont_weight(font_weight))
            text_item.setFont(font)
            text_item.setDefaultTextColor(QColor(text_color))
            text_item.setTextWidth(-1)

            rect = text_item.boundingRect()

            prepared_lines.append({
                "text_item": text_item,
                "rect": rect,
            })

        if not prepared_lines:
            return

        total_height = 0
        for line in prepared_lines:
            rect = line["rect"]
            bg_height = rect.height() + (padding_y * 2)
            total_height += bg_height

        total_height += section_gap * (len(prepared_lines) - 1)

        current_y = view_height - bottom_margin - total_height

        for line in prepared_lines:
            text_item = line["text_item"]
            rect = line["rect"]

            bg_width = rect.width() + (padding_x * 2)
            bg_height = rect.height() + (padding_y * 2)

            bg_x = (view_width - bg_width) / 2
            bg_y = current_y

            bg_item = QGraphicsRectItem(QRectF(bg_x, bg_y, bg_width, bg_height))
            bg_item.setBrush(QBrush(QColor(0, 0, 0, 160)))
            bg_item.setPen(QPen(Qt.PenStyle.NoPen))
            bg_item.setZValue(10)
            self.scene.addItem(bg_item)

            text_x = bg_x + (bg_width - rect.width()) / 2
            text_y = bg_y + (bg_height - rect.height()) / 2

            text_item.setPos(text_x, text_y)
            text_item.setZValue(11)
            self.scene.addItem(text_item)

            self.caption_background_items.append(bg_item)
            self.caption_text_items.append(text_item)

            current_y += bg_height + section_gap