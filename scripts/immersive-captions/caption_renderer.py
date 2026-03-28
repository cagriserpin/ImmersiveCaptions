from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsRectItem


SECTION_GAP = 0
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


def ease_in_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, float(t)))

    if t < 0.5:
        return 4.0 * t * t * t

    return 1.0 - ((-2.0 * t + 2.0) ** 3) / 2.0


def ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, float(t)))
    return 1.0 - ((1.0 - t) ** 3)


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

        self.current_group = None
        self.current_scene_size = None
        self.section_entries = []

    def clear(self) -> None:
        for entry in self.section_entries:
            bg_item = entry["background_item"]
            self.scene.removeItem(bg_item)

            for item in entry["items"]:
                self.scene.removeItem(item)

        self.section_entries.clear()
        self.current_group = None
        self.current_scene_size = None

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

    def compute_progress_from_range(self, start, end, time_seconds: float) -> float:
        if start is not None and end is not None:
            start = float(start)
            end = float(end)

            if time_seconds <= start:
                return 0.0
            if time_seconds >= end:
                return 1.0

            duration = max(0.001, end - start)
            return (time_seconds - start) / duration

        if start is not None:
            return 1.0 if time_seconds >= float(start) else 0.0

        if end is not None:
            return 1.0 if time_seconds >= float(end) else 0.0

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

    def resolve_scale_factor(self, animation_owner: dict, progress: float) -> float:
        animations = self.normalize_animation_list(animation_owner.get("animation"))
        scale_factor = 1.0

        for animation in animations:
            animation_type = animation.get("type")

            if animation_type == "scale":
                target_scale = float(animation.get("scale", 1.25))
                target_scale = max(0.01, target_scale)

                pulse_t = 1.0 - abs((progress * 2.0) - 1.0)
                eased_pulse = ease_in_out_cubic(pulse_t)

                animated_scale = 1.0 + ((target_scale - 1.0) * eased_pulse)
                scale_factor *= animated_scale

            elif animation_type == "pop":
                peak_scale = float(animation.get("scale", 1.25))
                peak_scale = max(0.01, peak_scale)

                attack_portion = 0.18

                if progress <= 0.0 or progress >= 1.0:
                    pop_amount = 0.0
                elif progress < attack_portion:
                    attack_t = progress / attack_portion
                    pop_amount = ease_out_cubic(attack_t)
                else:
                    decay_t = (progress - attack_portion) / max(0.001, 1.0 - attack_portion)
                    pop_amount = 1.0 - ease_in_out_cubic(decay_t)

                animated_scale = 1.0 + ((peak_scale - 1.0) * pop_amount)
                scale_factor *= animated_scale

        return scale_factor

    def get_default_dim_opacity(self, defaults: dict) -> float:
        return float(defaults.get("dim_opacity", 0.35))

    def create_word_item(self, text: str, font: QFont, dim_hex: str, active_color: str) -> WordGraphicsItem:
        item = WordGraphicsItem(text, font, dim_hex, active_color)
        item.setZValue(11)
        self.scene.addItem(item)
        return item

    def build_font(self, font_name: str, font_size: int, font_weight: int) -> QFont:
        font = QFont(font_name)
        font.setPointSize(font_size)
        font.setWeight(to_qfont_weight(font_weight))
        return font

    def build_dialogue_word_item_meta(self, section: dict, word: dict, defaults: dict, speakers: dict) -> dict | None:
        word_text = word.get("text", "")
        if not word_text:
            return None

        style = self.resolve_dialogue_style(section, word, defaults, speakers)
        font = self.build_font(style["font"], style["font_size"], style["font_weight"])

        active_color = style["font_color"]
        dim_hex = dim_color(active_color, self.get_default_dim_opacity(defaults))

        item = self.create_word_item(word_text, font, dim_hex, active_color)
        rect = item.boundingRect()

        return {
            "item": item,
            "owner": word,
            "base_width": rect.width(),
            "base_height": rect.height(),
        }

    def build_sfx_item_meta(self, section: dict, defaults: dict) -> dict | None:
        text = section.get("text", "")
        if not text:
            return None

        default_font = defaults.get("font", "Arial")
        default_font_size = int(defaults.get("font_size", 42))
        default_font_weight = int(defaults.get("font_weight", 400))
        default_font_color = defaults.get("font_color", "#ffffff")

        font_name = section.get("font", default_font)
        font_size = int(section.get("font_size", default_font_size))
        font_weight = int(section.get("font_weight", default_font_weight))
        font_color = section.get("font_color", default_font_color)

        dim_hex = dim_color(font_color, self.get_default_dim_opacity(defaults))
        font = self.build_font(font_name, font_size, font_weight)

        item = self.create_word_item(text, font, dim_hex, font_color)
        rect = item.boundingRect()

        return {
            "item": item,
            "owner": section,
            "base_width": rect.width(),
            "base_height": rect.height(),
        }

    def build_dialogue_section_entry(self, section: dict, defaults: dict, speakers: dict, background_item: QGraphicsRectItem) -> dict:
        items = []
        item_meta = []

        for word in section.get("words", []):
            meta = self.build_dialogue_word_item_meta(section, word, defaults, speakers)
            if meta is None:
                continue

            items.append(meta["item"])
            item_meta.append(meta)

        return {
            "type": "dialogue",
            "section": section,
            "background_item": background_item,
            "items": items,
            "item_meta": item_meta,
        }

    def build_sfx_section_entry(self, section: dict, defaults: dict, background_item: QGraphicsRectItem) -> dict:
        meta = self.build_sfx_item_meta(section, defaults)

        if meta is None:
            return {
                "type": "sfx",
                "section": section,
                "background_item": background_item,
                "items": [],
                "item_meta": [],
            }

        return {
            "type": "sfx",
            "section": section,
            "background_item": background_item,
            "items": [meta["item"]],
            "item_meta": [meta],
        }

    def create_background_item(self) -> QGraphicsRectItem:
        background_item = QGraphicsRectItem()
        background_item.setBrush(QBrush(QColor(0, 0, 0, 160)))
        background_item.setPen(QPen(Qt.PenStyle.NoPen))
        background_item.setZValue(10)
        self.scene.addItem(background_item)
        return background_item

    def build_group(self, group: dict) -> None:
        self.clear()
        self.current_group = group
        scene_rect = self.scene.sceneRect()
        self.current_scene_size = (scene_rect.width(), scene_rect.height())

        if self.caption_model is None:
            return

        defaults = self.caption_model.get_defaults()
        speakers = self.caption_model.get_speakers()

        for section in group.get("sections", []):
            section_type = section.get("type")
            background_item = self.create_background_item()

            if section_type == "dialogue":
                entry = self.build_dialogue_section_entry(section, defaults, speakers, background_item)
            elif section_type == "sfx":
                entry = self.build_sfx_section_entry(section, defaults, background_item)
            else:
                entry = {
                    "type": section_type,
                    "section": section,
                    "background_item": background_item,
                    "items": [],
                    "item_meta": [],
                }

            self.section_entries.append(entry)

    def compute_section_bounds(self, entry: dict) -> tuple[float, float, list[dict]]:
        layout_data = []

        base_x = 0.0
        union_left = 0.0
        union_right = 0.0
        union_top = 0.0
        union_bottom = 0.0
        first = True

        item_meta = entry["item_meta"]

        for index, meta in enumerate(item_meta):
            item = meta["item"]
            base_width = meta["base_width"]
            base_height = meta["base_height"]

            center_x = base_x + (base_width / 2.0)
            center_y = base_height / 2.0

            scaled_width = base_width * item.scale_factor
            scaled_height = base_height * item.scale_factor

            animated_left = center_x - (scaled_width / 2.0)
            animated_right = center_x + (scaled_width / 2.0)
            animated_top = center_y - (scaled_height / 2.0)
            animated_bottom = center_y + (scaled_height / 2.0)

            if first:
                union_left = animated_left
                union_right = animated_right
                union_top = animated_top
                union_bottom = animated_bottom
                first = False
            else:
                union_left = min(union_left, animated_left)
                union_right = max(union_right, animated_right)
                union_top = min(union_top, animated_top)
                union_bottom = max(union_bottom, animated_bottom)

            layout_data.append({
                "item": item,
                "base_x": base_x,
                "base_width": base_width,
                "base_height": base_height,
            })

            base_x += base_width
            if index < len(item_meta) - 1:
                base_x += WORD_GAP

        content_width = union_right - union_left
        content_height = union_bottom - union_top

        for data in layout_data:
            data["union_left"] = union_left
            data["union_top"] = union_top

        return content_width, content_height, layout_data

    def apply_item_animation_state(self, item: WordGraphicsItem, owner: dict, time_seconds: float) -> None:
        progress = self.compute_progress_from_range(owner.get("start"), owner.get("end"), time_seconds)
        scale_factor = self.resolve_scale_factor(owner, progress)

        item.set_reveal_progress(progress)
        item.set_scale_factor(scale_factor)

    def update_entry_animation_state(self, entry: dict, time_seconds: float) -> None:
        for meta in entry["item_meta"]:
            item = meta["item"]
            owner = meta["owner"]
            self.apply_item_animation_state(item, owner, time_seconds)

    def prepare_section_layout_data(self, entry: dict) -> dict:
        content_width, content_height, layout_data = self.compute_section_bounds(entry)

        return {
            "entry": entry,
            "content_width": content_width,
            "content_height": content_height,
            "layout_data": layout_data,
        }

    def layout_section(self, section_data: dict, current_y: float, view_width: float) -> float:
        entry = section_data["entry"]
        background_item = entry["background_item"]

        content_width = section_data["content_width"]
        content_height = section_data["content_height"]
        layout_data = section_data["layout_data"]

        bg_width = content_width + (PADDING_X * 2)
        bg_height = content_height + (PADDING_Y * 2)

        bg_x = (view_width - bg_width) / 2.0
        bg_y = current_y

        background_item.setRect(QRectF(bg_x, bg_y, bg_width, bg_height))

        content_x = bg_x + PADDING_X
        content_y = bg_y + PADDING_Y

        for data in layout_data:
            item = data["item"]
            base_x = data["base_x"]
            union_left = data["union_left"]
            union_top = data["union_top"]

            item_x = content_x + (base_x - union_left)
            item_y = content_y + (0.0 - union_top)

            item.setPos(item_x, item_y)

        return current_y + bg_height + SECTION_GAP

    def update_group_items(self, time_seconds: float) -> None:
        if self.caption_model is None or self.current_group is None:
            return

        view_width = self.scene.sceneRect().width()
        view_height = self.scene.sceneRect().height()

        prepared_sections = []

        for entry in self.section_entries:
            self.update_entry_animation_state(entry, time_seconds)
            prepared_sections.append(self.prepare_section_layout_data(entry))

        if not prepared_sections:
            return

        total_height = 0.0
        for section_data in prepared_sections:
            total_height += section_data["content_height"] + (PADDING_Y * 2)

        total_height += SECTION_GAP * (len(prepared_sections) - 1)

        current_y = view_height - BOTTOM_MARGIN - total_height

        for section_data in prepared_sections:
            current_y = self.layout_section(section_data, current_y, view_width)

    def render(self, time_seconds: float) -> None:
        if self.caption_model is None:
            return

        active_group = self.caption_model.get_active_group(time_seconds)
        scene_rect = self.scene.sceneRect()
        scene_size = (scene_rect.width(), scene_rect.height())

        if active_group is None:
            if self.current_group is not None:
                self.clear()
            return

        if self.current_group is not active_group or self.current_scene_size != scene_size:
            self.build_group(active_group)

        self.update_group_items(time_seconds)