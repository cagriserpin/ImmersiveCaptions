import math

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


class WordGraphicsItem(QGraphicsItem):
    def __init__(self, text: str, font: QFont, dim_color_hex: str, active_color_hex: str) -> None:
        super().__init__()

        self.text = text
        self.font = font
        self.dim_color = QColor(dim_color_hex)
        self.active_color = QColor(active_color_hex)

        self.reveal_progress = 0.0
        self.scale_factor = 1.0
        self.offset_y = 0.0
        self.rotation_deg = 0.0

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

    def set_offset_y(self, offset_y: float) -> None:
        offset_y = float(offset_y)
        if abs(offset_y - self.offset_y) > 1e-6:
            self.offset_y = offset_y

    def set_rotation_deg(self, rotation_deg: float) -> None:
        rotation_deg = float(rotation_deg)
        if abs(rotation_deg - self.rotation_deg) > 1e-6:
            self.rotation_deg = rotation_deg
            self.update()

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setFont(self.font)

        baseline_y = self.ascent
        center_x = self.text_width / 2.0
        center_y = self.text_height / 2.0

        painter.save()
        painter.translate(center_x, center_y)
        painter.rotate(self.rotation_deg)
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
            self.scene.removeItem(entry["background_item"])
            for item in entry["items"]:
                self.scene.removeItem(item)

        self.section_entries.clear()
        self.current_group = None
        self.current_scene_size = None

    def get_default_dim_opacity(self, defaults: dict) -> float:
        return float(defaults.get("dim_opacity", 0.35))

    def build_font(self, font_name: str, font_size: int, font_weight: int) -> QFont:
        font = QFont(font_name)
        font.setPointSize(font_size)
        font.setWeight(to_qfont_weight(font_weight))
        return font

    def normalize_animation_list(self, animation_value) -> list[dict]:
        return self.caption_model.normalize_animation_list(animation_value)

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

    def create_background_item(self) -> QGraphicsRectItem:
        background_item = QGraphicsRectItem()
        background_item.setBrush(QBrush(QColor(0, 0, 0, 160)))
        background_item.setPen(QPen(Qt.PenStyle.NoPen))
        background_item.setZValue(10)
        self.scene.addItem(background_item)
        return background_item

    def create_word_item(self, text: str, font: QFont, dim_hex: str, active_color: str) -> WordGraphicsItem:
        item = WordGraphicsItem(text, font, dim_hex, active_color)
        item.setZValue(11)
        self.scene.addItem(item)
        return item

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

    def max_scale_for_owner(self, owner: dict) -> float:
        animations = self.normalize_animation_list(owner.get("animation"))
        max_scale = 1.0

        for animation in animations:
            animation_type = animation.get("type")
            if animation_type in ("scale", "pop"):
                target_scale = float(animation.get("scale", 1.25))
                target_scale = max(0.01, target_scale)
                max_scale = max(max_scale, target_scale)

        return max_scale

    def max_vertical_amplitude_for_owner(self, owner: dict) -> float:
        animations = self.normalize_animation_list(owner.get("animation"))
        max_amplitude = 0.0

        for animation in animations:
            animation_type = animation.get("type")

            if animation_type == "bounce":
                amplitude_px = float(animation.get("amplitude_px", 8))
                amplitude_px = max(0.0, amplitude_px)
                max_amplitude = max(max_amplitude, amplitude_px)

            elif animation_type == "jiggle":
                angle_deg = float(animation.get("angle_deg", 5))
                angle_deg = max(0.0, abs(angle_deg))
                # simple extra padding estimate for rotation
                estimated_extra = 6.0 + angle_deg
                max_amplitude = max(max_amplitude, estimated_extra)

        return max_amplitude

    def compute_reserved_section_layout(self, entry: dict) -> dict:
        item_meta = entry["item_meta"]
        if not item_meta:
            return {
                "reserved_content_width": 0.0,
                "reserved_content_height": 0.0,
                "slot_layout": [],
            }

        slot_layout = []
        current_x = 0.0
        max_reserved_height = 0.0

        for index, meta in enumerate(item_meta):
            owner = meta["owner"]
            base_width = meta["base_width"]
            base_height = meta["base_height"]

            max_scale = self.max_scale_for_owner(owner)
            max_amplitude = self.max_vertical_amplitude_for_owner(owner)

            reserved_width = base_width * max_scale
            reserved_height = (base_height * max_scale) + (2.0 * max_amplitude)

            slot_layout.append({
                "item": meta["item"],
                "owner": owner,
                "base_width": base_width,
                "base_height": base_height,
                "slot_x": current_x,
                "slot_width": reserved_width,
                "reserved_height": reserved_height,
            })

            current_x += reserved_width
            if index < len(item_meta) - 1:
                current_x += WORD_GAP

            max_reserved_height = max(max_reserved_height, reserved_height)

        for slot in slot_layout:
            slot["slot_y"] = (max_reserved_height - slot["reserved_height"]) / 2.0
            slot["base_x_in_slot"] = (slot["slot_width"] - slot["base_width"]) / 2.0
            slot["base_y_in_slot"] = (slot["reserved_height"] - slot["base_height"]) / 2.0

        return {
            "reserved_content_width": current_x,
            "reserved_content_height": max_reserved_height,
            "slot_layout": slot_layout,
        }

    def layout_group_static(self) -> None:
        if not self.section_entries:
            return

        view_width = self.scene.sceneRect().width()
        view_height = self.scene.sceneRect().height()

        total_height = 0.0
        for entry in self.section_entries:
            total_height += entry["reserved_content_height"] + (PADDING_Y * 2)

        total_height += SECTION_GAP * (len(self.section_entries) - 1)

        current_y = view_height - BOTTOM_MARGIN - total_height

        for entry in self.section_entries:
            content_width = entry["reserved_content_width"]
            content_height = entry["reserved_content_height"]

            bg_width = content_width + (PADDING_X * 2)
            bg_height = content_height + (PADDING_Y * 2)

            bg_x = (view_width - bg_width) / 2.0
            bg_y = current_y

            entry["background_item"].setRect(QRectF(bg_x, bg_y, bg_width, bg_height))

            content_x = bg_x + PADDING_X
            content_y = bg_y + PADDING_Y

            for slot in entry["slot_layout"]:
                item = slot["item"]
                item_x = content_x + slot["slot_x"] + slot["base_x_in_slot"]
                item_y = content_y + slot["slot_y"] + slot["base_y_in_slot"]
                item.setPos(item_x, item_y)

            current_y += bg_height + SECTION_GAP

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

            reserved_layout = self.compute_reserved_section_layout(entry)
            entry["reserved_content_width"] = reserved_layout["reserved_content_width"]
            entry["reserved_content_height"] = reserved_layout["reserved_content_height"]
            entry["slot_layout"] = reserved_layout["slot_layout"]

            self.section_entries.append(entry)

        self.layout_group_static()

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
                target_scale = float(animation.get("scale", 1.25))
                target_scale = max(0.01, target_scale)

                attack_portion = 0.18

                if progress <= 0.0 or progress >= 1.0:
                    pop_amount = 0.0
                elif progress < attack_portion:
                    attack_t = progress / attack_portion
                    pop_amount = ease_in_out_cubic(attack_t)
                else:
                    decay_t = (progress - attack_portion) / max(0.001, 1.0 - attack_portion)
                    pop_amount = 1.0 - ease_in_out_cubic(decay_t)

                animated_scale = 1.0 + ((target_scale - 1.0) * pop_amount)
                scale_factor *= animated_scale

        return scale_factor

    def resolve_vertical_offset(self, animation_owner: dict, progress: float) -> float:
        animations = self.normalize_animation_list(animation_owner.get("animation"))
        offset_y = 0.0

        for animation in animations:
            if animation.get("type") == "bounce":
                amplitude_px = float(animation.get("amplitude_px", 8))
                cycles = float(animation.get("cycles", 2))
                direction = animation.get("direction", "up")

                amplitude_px = max(0.0, amplitude_px)
                cycles = max(0.0, cycles)

                if amplitude_px <= 0.0 or cycles <= 0.0:
                    continue

                pulse_t = 1.0 - abs((progress * 2.0) - 1.0)
                eased_envelope = ease_in_out_cubic(pulse_t)

                if direction == "up":
                    # one upward arc per cycle
                    oscillation = -abs(math.sin(progress * cycles * math.pi))
                elif direction == "down":
                    # one downward arc per cycle
                    oscillation = abs(math.sin(progress * cycles * math.pi))
                else:
                    # one full up-down oscillation per cycle
                    oscillation = math.sin(progress * cycles * 2.0 * math.pi)

                offset_y += amplitude_px * eased_envelope * oscillation

        return offset_y

    def resolve_rotation_deg(self, animation_owner: dict, progress: float) -> float:
        animations = self.normalize_animation_list(animation_owner.get("animation"))
        rotation_deg = 0.0

        for animation in animations:
            if animation.get("type") == "jiggle":
                angle_deg = float(animation.get("angle_deg", 5))
                cycles = float(animation.get("cycles", 3))

                angle_deg = max(0.0, abs(angle_deg))
                cycles = max(0.0, cycles)

                if angle_deg <= 0.0 or cycles <= 0.0:
                    continue

                pulse_t = 1.0 - abs((progress * 2.0) - 1.0)
                eased_envelope = ease_in_out_cubic(pulse_t)
                oscillation = math.sin(progress * cycles * 2.0 * math.pi)

                rotation_deg += angle_deg * eased_envelope * oscillation

        return rotation_deg

    def apply_item_animation_state(self, item: WordGraphicsItem, owner: dict, time_seconds: float) -> None:
        progress = self.caption_model.compute_owner_effective_progress(owner, time_seconds)
        scale_factor = self.resolve_scale_factor(owner, progress)
        offset_y = self.resolve_vertical_offset(owner, progress)
        rotation_deg = self.resolve_rotation_deg(owner, progress)

        item.set_reveal_progress(progress)
        item.set_scale_factor(scale_factor)
        item.set_offset_y(offset_y)
        item.set_rotation_deg(rotation_deg)

    def update_group_items(self, time_seconds: float) -> None:
        if self.caption_model is None or self.current_group is None:
            return

        for entry in self.section_entries:
            background_rect = entry["background_item"].rect()

            for slot in entry["slot_layout"]:
                item = slot["item"]
                owner = slot["owner"]

                self.apply_item_animation_state(item, owner, time_seconds)

                static_x = (
                    background_rect.x()
                    + PADDING_X
                    + slot["slot_x"]
                    + slot["base_x_in_slot"]
                )
                static_y = (
                    background_rect.y()
                    + PADDING_Y
                    + slot["slot_y"]
                    + slot["base_y_in_slot"]
                )

                item.setPos(static_x, static_y + item.offset_y)

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