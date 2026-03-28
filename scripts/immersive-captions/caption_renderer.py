from html import escape

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


def parse_hex_color(color_string: str) -> tuple[int, int, int]:
    color_string = color_string.strip()

    if color_string.startswith("#"):
        color_string = color_string[1:]

    if len(color_string) != 6:
        return 255, 255, 255

    try:
        r = int(color_string[0:2], 16)
        g = int(color_string[2:4], 16)
        b = int(color_string[4:6], 16)
        return r, g, b
    except ValueError:
        return 255, 255, 255


def rgb_to_hex(r: int, g: int, b: int) -> str:
    r = max(0, min(255, r))
    g = max(0, min(255, g))
    b = max(0, min(255, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def dim_color(color_string: str, dim_opacity: float) -> str:
    r, g, b = parse_hex_color(color_string)

    factor = max(0.0, min(1.0, float(dim_opacity)))
    dim_r = int(r * factor)
    dim_g = int(g * factor)
    dim_b = int(b * factor)

    return rgb_to_hex(dim_r, dim_g, dim_b)


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

    def build_dialogue_html(
        self,
        section: dict,
        time_seconds: float,
        defaults: dict,
        speakers: dict,
    ) -> str:
        default_font = defaults.get("font", "Arial")
        default_font_size = int(defaults.get("font_size", 42))
        default_font_weight = int(defaults.get("font_weight", 400))
        default_font_color = defaults.get("font_color", "#ffffff")
        default_dim_opacity = float(defaults.get("dim_opacity", 0.35))

        speaker_name = section.get("speaker")
        speaker_defaults = speakers.get(speaker_name, {})

        base_font = section.get("font", speaker_defaults.get("font", default_font))
        base_font_size = int(section.get("font_size", speaker_defaults.get("font_size", default_font_size)))
        base_font_weight = int(section.get("font_weight", speaker_defaults.get("font_weight", default_font_weight)))
        base_font_color = section.get("font_color", speaker_defaults.get("font_color", default_font_color))

        words = section.get("words", [])
        spans = []

        for word in words:
            word_text = word.get("text", "")
            if not word_text:
                continue

            word_start = word.get("start")
            word_end = word.get("end")

            word_font = word.get("font", base_font)
            word_font_size = int(word.get("font_size", base_font_size))
            word_font_weight = int(word.get("font_weight", base_font_weight))
            word_font_color = word.get("font_color", base_font_color)

            is_spoken = False
            if word_end is not None:
                is_spoken = time_seconds >= float(word_end)
            elif word_start is not None:
                is_spoken = time_seconds >= float(word_start)

            render_color = word_font_color if is_spoken else dim_color(word_font_color, default_dim_opacity)

            span = (
                f'<span style="'
                f'font-family:\'{escape(str(word_font))}\'; '
                f'font-size:{word_font_size}pt; '
                f'font-weight:{word_font_weight}; '
                f'color:{render_color};'
                f'">{escape(word_text)}</span>'
            )
            spans.append(span)

        return " ".join(spans)

    def build_sfx_html(self, section: dict, defaults: dict) -> str:
        default_font = defaults.get("font", "Arial")
        default_font_size = int(defaults.get("font_size", 42))
        default_font_weight = int(defaults.get("font_weight", 400))
        default_font_color = defaults.get("font_color", "#ffffff")

        text = escape(section.get("text", ""))

        font = section.get("font", default_font)
        font_size = int(section.get("font_size", default_font_size))
        font_weight = int(section.get("font_weight", default_font_weight))
        font_color = section.get("font_color", default_font_color)

        return (
            f'<span style="'
            f'font-family:\'{escape(str(font))}\'; '
            f'font-size:{font_size}pt; '
            f'font-weight:{font_weight}; '
            f'color:{font_color};'
            f'">{text}</span>'
        )

    def build_section_html(self, section: dict, time_seconds: float, defaults: dict, speakers: dict) -> str:
        section_type = section.get("type")

        if section_type == "dialogue":
            return self.build_dialogue_html(section, time_seconds, defaults, speakers)

        if section_type == "sfx":
            return self.build_sfx_html(section, defaults)

        return ""

    def render(self, time_seconds: float) -> None:
        self.clear()

        if self.caption_model is None:
            return

        active_sections = self.caption_model.get_active_sections(time_seconds)
        if not active_sections:
            return

        defaults = self.caption_model.get_defaults()
        speakers = self.caption_model.get_speakers()

        view_width = self.scene.sceneRect().width()
        view_height = self.scene.sceneRect().height()

        section_gap = 14
        padding_x = 18
        padding_y = 10
        bottom_margin = 110

        prepared_lines = []

        for section in active_sections:
            html = self.build_section_html(section, time_seconds, defaults, speakers)
            if not html:
                continue

            text_item = QGraphicsTextItem()
            text_item.setHtml(html)
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