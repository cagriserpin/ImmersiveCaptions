from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsRectItem, QGraphicsTextItem


SECTION_GAP = 14
PADDING_X = 18
PADDING_Y = 10
BOTTOM_MARGIN = 110
WORD_GAP = 10
REVEAL_FEATHER_PX = 12


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


class WordGraphicsItem(QGraphicsItem):
    def __init__(self, text: str, font: QFont, dim_color_hex: str, active_color_hex: str) -> None:
        super().__init__()

        self.text = text
        self.font = font
        self.dim_color = QColor(dim_color_hex)
        self.active_color = QColor(active_color_hex)

        self.reveal_progress = 0.0
        self.scale_factor = 1.0

        self.metrics = QFontMetricsF(self.font)
        self.text_width = self.metrics.horizontalAdvance(self.text)
        self.text_height = self.metrics.height()
        self.ascent = self.metrics.ascent()

        self.bounds = QRectF(0, 0, self.text_width, self.text_height)

    def boundingRect(self) -> QRectF:
        return self.bounds

    def set_reveal_progress(self, progress: float) -> None:
        clamped = max(0.0, min(1.0, float(progress)))
        if abs(clamped - self.reveal_progress) > 1e-6:
            self.reveal_progress = clamped
            self.update()

    def set_scale_factor(self, scale_factor: float) -> None:
        scale_factor = max(0.01, float(scale_factor))
        if abs(scale_factor - self.scale_factor) > 1e-6:
            self.scale_factor = scale_factor
            self.update()

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setFont(self.font)

        baseline_y = self.ascent
        center_x = self.text_width / 2.0
        center_y = self.text_height / 2.0

        painter.save()
        painter.translate(center_x, center_y)
        painter.scale(self.scale_factor, self.scale_factor)
        painter.translate(-center_x, -center_y)

        painter.setPen(self.dim_color)
        painter.drawText(0, baseline_y, self.text)

        reveal_width = self.text_width * self.reveal_progress
        if reveal_width <= 0:
            painter.restore()
            return

        if self.reveal_progress >= 1.0:
            painter.setPen(self.active_color)
            painter.drawText(0, baseline_y, self.text)
            painter.restore()
            return

        feather_width = min(REVEAL_FEATHER_PX, self.text_width)

        solid_width = max(0.0, reveal_width - feather_width)

        if solid_width > 0:
            painter.save()
            painter.setClipRect(QRectF(0, 0, solid_width, self.text_height))
            painter.setPen(self.active_color)
            painter.drawText(0, baseline_y, self.text)
            painter.restore()

        feather_start = max(0.0, solid_width)
        feather_end = min(self.text_width, reveal_width)

        if feather_end > feather_start:
            painter.save()
            painter.setClipRect(QRectF(feather_start, 0, feather_end - feather_start, self.text_height))

            start_color = QColor(self.active_color)
            start_color.setAlpha(255)

            end_color = QColor(self.active_color)
            end_color.setAlpha(0)

            gradient = QLinearGradient(feather_start, 0, feather_end, 0)
            gradient.setColorAt(0.0, start_color)
            gradient.setColorAt(1.0, end_color)

            painter.setPen(QPen(QBrush(gradient), 0))
            painter.drawText(0, baseline_y, self.text)
            painter.restore()

        painter.restore()


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

    def resolve_dialogue_style(self, section: dict, word: dict, defaults: dict, speakers: dict) -> dict:
        default_font = defaults.get("font", "Arial")
        default_font_size = int(defaults.get("font_size", 42))
        default_font_weight = int(defaults.get("font_weight", 400))
        default_font_color = defaults.get("font_color", "#ffffff")

        speaker_name = section.get("speaker")
        speaker_defaults = speakers.get(speaker_name, {})

        resolved_font = word.get(
            "font",
            section.get("font", speaker_defaults.get("font", default_font)),
        )
        resolved_font_size = int(
            word.get(
                "font_size",
                section.get("font_size", speaker_defaults.get("font_size", default_font_size)),
            )
        )
        resolved_font_weight = int(
            word.get(
                "font_weight",
                section.get("font_weight", speaker_defaults.get("font_weight", default_font_weight)),
            )
        )
        resolved_font_color = word.get(
            "font_color",
            section.get("font_color", speaker_defaults.get("font_color", default_font_color)),
        )

        return {
            "font": resolved_font,
            "font_size": resolved_font_size,
            "font_weight": resolved_font_weight,
            "font_color": resolved_font_color,
        }

    def compute_word_progress(self, word: dict, time_seconds: float) -> float:
        word_start = word.get("start")
        word_end = word.get("end")

        if word_start is not None and word_end is not None:
            word_start = float(word_start)
            word_end = float(word_end)

            if time_seconds <= word_start:
                return 0.0
            if time_seconds >= word_end:
                return 1.0

            duration = max(0.001, word_end - word_start)
            return (time_seconds - word_start) / duration

        if word_start is not None:
            return 1.0 if time_seconds >= float(word_start) else 0.0

        if word_end is not None:
            return 1.0 if time_seconds >= float(word_end) else 0.0

        return 0.0

    def normalize_animation_list(self, animation_value) -> list[dict]:
        if animation_value is None:
            return []

        if isinstance(animation_value, str):
            return [{"type": animation_value}]

        if isinstance(animation_value, dict):
            return [animation_value]

        if isinstance(animation_value, list):
            normalized = []
            for entry in animation_value:
                if isinstance(entry, str):
                    normalized.append({"type": entry})
                elif isinstance(entry, dict) and "type" in entry:
                    normalized.append(entry)
            return normalized

        return []

    def resolve_word_scale_factor(self, word: dict, word_progress: float) -> float:
        animations = self.normalize_animation_list(word.get("animation"))
        scale_factor = 1.0

        for animation in animations:
            animation_type = animation.get("type")

            if animation_type == "scale":
                target_scale = float(animation.get("scale", 1.2))
                target_scale = max(0.01, target_scale)

                # Ease-in-out pulse:
                # progress 0.0 -> scale 1.0
                # progress 0.5 -> peak scale
                # progress 1.0 -> scale 1.0
                pulse = 1.0 - abs((word_progress * 2.0) - 1.0)
                animated_scale = 1.0 + ((target_scale - 1.0) * pulse)

                scale_factor *= animated_scale

        return scale_factor

    def build_dialogue_section_items(self, section: dict, time_seconds: float, defaults: dict, speakers: dict):
        default_dim_opacity = float(defaults.get("dim_opacity", 0.35))

        words = section.get("words", [])
        word_items = []

        for word in words:
            word_text = word.get("text", "")
            if not word_text:
                continue

            style = self.resolve_dialogue_style(section, word, defaults, speakers)

            font = QFont(style["font"])
            font.setPointSize(style["font_size"])
            font.setWeight(to_qfont_weight(style["font_weight"]))

            active_color = style["font_color"]
            dim_hex = dim_color(active_color, default_dim_opacity)
            progress = self.compute_word_progress(word, time_seconds)
            scale_factor = self.resolve_word_scale_factor(word, progress)

            item = WordGraphicsItem(word_text, font, dim_hex, active_color)
            item.set_reveal_progress(progress)
            item.set_scale_factor(scale_factor)

            word_items.append(item)

        return word_items

    def build_sfx_item(self, section: dict, time_seconds: float, defaults: dict):
        default_font = defaults.get("font", "Arial")
        default_font_size = int(defaults.get("font_size", 42))
        default_font_weight = int(defaults.get("font_weight", 400))
        default_font_color = defaults.get("font_color", "#ffffff")
        default_dim_opacity = float(defaults.get("dim_opacity", 0.35))

        text = section.get("text", "")
        if not text:
            return None

        font_name = section.get("font", default_font)
        font_size = int(section.get("font_size", default_font_size))
        font_weight = int(section.get("font_weight", default_font_weight))
        font_color = section.get("font_color", default_font_color)

        font = QFont(font_name)
        font.setPointSize(font_size)
        font.setWeight(to_qfont_weight(font_weight))

        dim_hex = dim_color(font_color, default_dim_opacity)

        start = section.get("start")
        end = section.get("end")

        if start is not None and end is not None:
            start = float(start)
            end = float(end)

            if time_seconds <= start:
                progress = 0.0
            elif time_seconds >= end:
                progress = 1.0
            else:
                duration = max(0.001, end - start)
                progress = (time_seconds - start) / duration
        elif start is not None:
            progress = 1.0 if time_seconds >= float(start) else 0.0
        elif end is not None:
            progress = 1.0 if time_seconds >= float(end) else 0.0
        else:
            progress = 0.0

        item = WordGraphicsItem(text, font, dim_hex, font_color)
        item.set_reveal_progress(progress)
        item.set_scale_factor(1.0)
        return item

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

        prepared_sections = []

        for section in active_sections:
            section_type = section.get("type")

            if section_type == "dialogue":
                word_items = self.build_dialogue_section_items(section, time_seconds, defaults, speakers)
                if not word_items:
                    continue

                content_width = 0.0
                content_height = 0.0

                for index, item in enumerate(word_items):
                    rect = item.boundingRect()
                    content_width += rect.width()
                    content_height = max(content_height, rect.height())

                    if index < len(word_items) - 1:
                        content_width += WORD_GAP

                prepared_sections.append({
                    "type": "dialogue",
                    "word_items": word_items,
                    "content_width": content_width,
                    "content_height": content_height,
                })

            elif section_type == "sfx":
                text_item = self.build_sfx_item(section, time_seconds, defaults)
                if text_item is None:
                    continue

                rect = text_item.boundingRect()

                prepared_sections.append({
                    "type": "sfx",
                    "text_item": text_item,
                    "content_width": rect.width(),
                    "content_height": rect.height(),
                })

        if not prepared_sections:
            return

        total_height = 0.0
        for section_data in prepared_sections:
            bg_height = section_data["content_height"] + (PADDING_Y * 2)
            total_height += bg_height

        total_height += SECTION_GAP * (len(prepared_sections) - 1)

        current_y = view_height - BOTTOM_MARGIN - total_height

        for section_data in prepared_sections:
            content_width = section_data["content_width"]
            content_height = section_data["content_height"]

            bg_width = content_width + (PADDING_X * 2)
            bg_height = content_height + (PADDING_Y * 2)

            bg_x = (view_width - bg_width) / 2
            bg_y = current_y

            bg_item = QGraphicsRectItem(QRectF(bg_x, bg_y, bg_width, bg_height))
            bg_item.setBrush(QBrush(QColor(0, 0, 0, 160)))
            bg_item.setPen(QPen(Qt.PenStyle.NoPen))
            bg_item.setZValue(10)
            self.scene.addItem(bg_item)
            self.caption_background_items.append(bg_item)

            content_x = bg_x + (bg_width - content_width) / 2
            content_y = bg_y + (bg_height - content_height) / 2

            if section_data["type"] == "dialogue":
                word_x = content_x

                for item in section_data["word_items"]:
                    rect = item.boundingRect()
                    word_y = content_y + (content_height - rect.height()) / 2

                    item.setPos(word_x, word_y)
                    item.setZValue(11)
                    self.scene.addItem(item)
                    self.caption_text_items.append(item)

                    word_x += rect.width() + WORD_GAP

            elif section_data["type"] == "sfx":
                text_item = section_data["text_item"]
                text_item.setPos(content_x, content_y)
                text_item.setZValue(11)
                self.scene.addItem(text_item)
                self.caption_text_items.append(text_item)

            current_y += bg_height + SECTION_GAP