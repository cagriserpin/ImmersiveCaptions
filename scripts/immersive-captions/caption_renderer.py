import math

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsRectItem


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
        return int(color_string[0:2], 16), int(color_string[2:4], 16), int(color_string[4:6], 16)
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
    return rgb_to_hex(int(r * factor), int(g * factor), int(b * factor))


def ease_in_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, float(t)))
    if t < 0.5:
        return 4.0 * t * t * t
    return 1.0 - ((-2.0 * t + 2.0) ** 3) / 2.0


class WordGraphicsItem(QGraphicsItem):
    def __init__(self, text: str, font: QFont, dim_color_hex: str, active_color_hex: str, reveal_feather_px: float) -> None:
        super().__init__()

        self.text = text
        self.font = font
        self.dim_color = QColor(dim_color_hex)
        self.active_color = QColor(active_color_hex)
        self.reveal_feather_px = max(0.0, float(reveal_feather_px))

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

        feather_width = min(self.reveal_feather_px, self.text_width)
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

        self.current_group_set = tuple()
        self.current_scene_size = None
        self.group_entries = []

    def clear(self) -> None:
        for group_entry in self.group_entries:
            for section_entry in group_entry["section_entries"]:
                self.scene.removeItem(section_entry["background_item"])
                for item in section_entry["items"]:
                    self.scene.removeItem(item)

        self.group_entries.clear()
        self.current_group_set = tuple()
        self.current_scene_size = None

    def resolve_layout_defaults(
        self,
        group: dict | None = None,
        section: dict | None = None,
        word: dict | None = None,
    ) -> dict:
        return self.caption_model.get_style_defaults_for_context(
            group=group,
            section=section,
            word=word,
            speaker_name=None,
            include_word_defaults=(word is not None),
        )

    def get_group_gap(self, group: dict | None = None) -> float:
        defaults = self.resolve_layout_defaults(group=group)
        return float(defaults.get("group_gap", 0.0))

    def get_section_gap(self, group: dict | None = None, section: dict | None = None) -> float:
        defaults = self.resolve_layout_defaults(group=group, section=section)
        return float(defaults.get("section_gap", 0.0))

    def get_section_to_bg_padding_x(self, group: dict | None = None, section: dict | None = None) -> float:
        defaults = self.resolve_layout_defaults(group=group, section=section)
        return float(defaults.get("section_to_bg_padding_x", 0.0))

    def get_section_to_bg_padding_y(self, group: dict | None = None, section: dict | None = None) -> float:
        defaults = self.resolve_layout_defaults(group=group, section=section)
        return float(defaults.get("section_to_bg_padding_y", 0.0))

    def get_section_video_bottom_margin(self, group: dict | None = None) -> float:
        defaults = self.resolve_layout_defaults(group=group)
        return float(defaults.get("section_video_bottom_margin", 0.0))

    def get_word_gap(self, group: dict | None = None, section: dict | None = None, word: dict | None = None) -> float:
        defaults = self.resolve_layout_defaults(group=group, section=section, word=word)
        return float(defaults.get("word_gap", 0.0))

    def get_reveal_feather_px(self, group: dict | None = None, section: dict | None = None, word: dict | None = None) -> float:
        defaults = self.resolve_layout_defaults(group=group, section=section, word=word)
        return float(defaults.get("reveal_feather_px", 0.0))

    def get_default_dim_opacity(self, style_dict: dict) -> float:
        return float(style_dict.get("dim_opacity", 0.35))

    def build_font(self, font_name: str, font_size: int, font_weight: int, font_style: str = "normal") -> QFont:
        font = QFont(font_name)
        font.setPointSize(int(font_size))
        font.setWeight(to_qfont_weight(int(font_weight)))

        style_value = str(font_style).strip().lower()

        if style_value == "italic":
            font.setItalic(True)
        else:
            font.setItalic(False)

        return font

    def create_background_item(self) -> QGraphicsRectItem:
        background_item = QGraphicsRectItem()
        background_item.setBrush(QBrush(QColor(0, 0, 0, 160)))
        background_item.setPen(QPen(Qt.PenStyle.NoPen))
        background_item.setZValue(10)
        self.scene.addItem(background_item)
        return background_item

    def create_word_item(self, text: str, font: QFont, dim_hex: str, active_color: str, reveal_feather_px: float) -> WordGraphicsItem:
        item = WordGraphicsItem(text, font, dim_hex, active_color, reveal_feather_px)
        item.setZValue(11)
        self.scene.addItem(item)
        return item

    def build_dialogue_word_item_meta(self, group: dict, section: dict, word: dict, defaults: dict) -> dict | None:
        word_text = word.get("text", "")
        if not word_text:
            return None

        style = self.caption_model.resolve_dialogue_style(group, section, word)
        merged_style = {**defaults, **style}

        font = self.build_font(
            merged_style.get("font", "Arial"),
            merged_style.get("font_size", 42),
            merged_style.get("font_weight", 400),
            merged_style.get("font_style", "normal"),
        )

        active_color = merged_style.get("font_color", "#ffffff")
        dim_hex = dim_color(active_color, self.get_default_dim_opacity(merged_style))
        reveal_feather_px = self.get_reveal_feather_px(group=group, section=section, word=word)

        resolved_animations = self.caption_model.get_resolved_animation_list(
            word,
            group=group,
            section=section,
            word=word,
        )

        item = self.create_word_item(word_text, font, dim_hex, active_color, reveal_feather_px)
        rect = item.boundingRect()

        return {
            "item": item,
            "owner": word,
            "resolved_animations": resolved_animations,
            "base_width": rect.width(),
            "base_height": rect.height(),
            "word_gap": self.get_word_gap(group=group, section=section, word=word),
        }

    def build_sfx_item_meta(self, group: dict, section: dict, defaults: dict) -> dict | None:
        text = section.get("text", "")
        if not text:
            return None

        style = self.caption_model.resolve_sfx_style(group, section)
        merged_style = {**defaults, **style}

        font = self.build_font(
            merged_style.get("font", "Arial"),
            merged_style.get("font_size", 42),
            merged_style.get("font_weight", 400),
            merged_style.get("font_style", "normal"),
        )

        active_color = merged_style.get("font_color", "#ffffff")
        dim_hex = dim_color(active_color, self.get_default_dim_opacity(merged_style))
        reveal_feather_px = self.get_reveal_feather_px(group=group, section=section)

        resolved_animations = self.caption_model.get_resolved_animation_list(
            section,
            group=group,
            section=section,
            word=None,
        )

        item = self.create_word_item(text, font, dim_hex, active_color, reveal_feather_px)
        rect = item.boundingRect()

        return {
            "item": item,
            "owner": section,
            "resolved_animations": resolved_animations,
            "base_width": rect.width(),
            "base_height": rect.height(),
            "word_gap": self.get_word_gap(group=group, section=section),
        }

    def build_dialogue_section_entry(self, group: dict, section: dict, defaults: dict, background_item: QGraphicsRectItem) -> dict:
        items = []
        item_meta = []

        for word in section.get("words", []):
            meta = self.build_dialogue_word_item_meta(group, section, word, defaults)
            if meta is None:
                continue
            items.append(meta["item"])
            item_meta.append(meta)

        return {
            "type": "dialogue",
            "group": group,
            "section": section,
            "background_item": background_item,
            "items": items,
            "item_meta": item_meta,
            "section_gap": self.get_section_gap(group=group, section=section),
            "padding_x": self.get_section_to_bg_padding_x(group=group, section=section),
            "padding_y": self.get_section_to_bg_padding_y(group=group, section=section),
        }

    def build_sfx_section_entry(self, group: dict, section: dict, defaults: dict, background_item: QGraphicsRectItem) -> dict:
        meta = self.build_sfx_item_meta(group, section, defaults)

        if meta is None:
            return {
                "type": "sfx",
                "group": group,
                "section": section,
                "background_item": background_item,
                "items": [],
                "item_meta": [],
                "section_gap": self.get_section_gap(group=group, section=section),
                "padding_x": self.get_section_to_bg_padding_x(group=group, section=section),
                "padding_y": self.get_section_to_bg_padding_y(group=group, section=section),
            }

        return {
            "type": "sfx",
            "group": group,
            "section": section,
            "background_item": background_item,
            "items": [meta["item"]],
            "item_meta": [meta],
            "section_gap": self.get_section_gap(group=group, section=section),
            "padding_x": self.get_section_to_bg_padding_x(group=group, section=section),
            "padding_y": self.get_section_to_bg_padding_y(group=group, section=section),
        }

    def max_scale_for_resolved_animations(self, resolved_animations: list[dict]) -> float:
        max_scale = 1.0
        for animation in resolved_animations:
            animation_type = animation.get("type")
            if animation_type in ("scale", "pop"):
                target_scale = float(animation.get("scale", 1.25))
                max_scale = max(max_scale, max(0.01, target_scale))
        return max_scale

    def max_vertical_amplitude_for_resolved_animations(self, resolved_animations: list[dict]) -> float:
        max_amplitude = 0.0

        for animation in resolved_animations:
            animation_type = animation.get("type")

            if animation_type == "bounce":
                amplitude_px = float(animation.get("amplitude_px", 8))
                max_amplitude = max(max_amplitude, max(0.0, amplitude_px))
            elif animation_type == "jiggle":
                angle_deg = float(animation.get("angle_deg", 5))
                max_amplitude = max(max_amplitude, 6.0 + max(0.0, abs(angle_deg)))

        return max_amplitude

    def compute_reserved_section_layout(self, section_entry: dict) -> dict:
        item_meta = section_entry["item_meta"]
        if not item_meta:
            return {"reserved_content_width": 0.0, "reserved_content_height": 0.0, "slot_layout": []}

        slot_layout = []
        current_x = 0.0
        max_reserved_height = 0.0

        for index, meta in enumerate(item_meta):
            resolved_animations = meta["resolved_animations"]
            base_width = meta["base_width"]
            base_height = meta["base_height"]
            word_gap = meta["word_gap"]

            max_scale = self.max_scale_for_resolved_animations(resolved_animations)
            max_amplitude = self.max_vertical_amplitude_for_resolved_animations(resolved_animations)

            reserved_width = base_width * max_scale
            reserved_height = (base_height * max_scale) + (2.0 * max_amplitude)

            slot_layout.append({
                "item": meta["item"],
                "owner": meta["owner"],
                "resolved_animations": resolved_animations,
                "base_width": base_width,
                "base_height": base_height,
                "slot_x": current_x,
                "slot_width": reserved_width,
                "reserved_height": reserved_height,
            })

            current_x += reserved_width
            if index < len(item_meta) - 1:
                current_x += word_gap

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

    def compute_group_layout_metrics(self, section_entries: list[dict]) -> dict:
        total_height = 0.0
        max_width = 0.0

        for entry in section_entries:
            bg_height = entry["reserved_content_height"] + (entry["padding_y"] * 2)
            bg_width = entry["reserved_content_width"] + (entry["padding_x"] * 2)
            total_height += bg_height
            max_width = max(max_width, bg_width)

        for index, entry in enumerate(section_entries[:-1]):
            total_height += entry["section_gap"]

        return {
            "group_total_height": total_height,
            "group_max_width": max_width,
        }

    def build_group_entry(self, group: dict) -> dict:
        defaults = self.caption_model.get_root_defaults()
        section_entries = []

        for section in group.get("sections", []):
            section_type = section.get("type")
            background_item = self.create_background_item()

            if section_type == "dialogue":
                entry = self.build_dialogue_section_entry(group, section, defaults, background_item)
            elif section_type == "sfx":
                entry = self.build_sfx_section_entry(group, section, defaults, background_item)
            else:
                entry = {
                    "type": section_type,
                    "group": group,
                    "section": section,
                    "background_item": background_item,
                    "items": [],
                    "item_meta": [],
                    "section_gap": self.get_section_gap(group=group, section=section),
                    "padding_x": self.get_section_to_bg_padding_x(group=group, section=section),
                    "padding_y": self.get_section_to_bg_padding_y(group=group, section=section),
                }

            reserved_layout = self.compute_reserved_section_layout(entry)
            entry["reserved_content_width"] = reserved_layout["reserved_content_width"]
            entry["reserved_content_height"] = reserved_layout["reserved_content_height"]
            entry["slot_layout"] = reserved_layout["slot_layout"]

            section_entries.append(entry)

        metrics = self.compute_group_layout_metrics(section_entries)

        return {
            "group": group,
            "section_entries": section_entries,
            "group_total_height": metrics["group_total_height"],
            "group_max_width": metrics["group_max_width"],
            "group_gap": self.get_group_gap(group=group),
            "bottom_margin": self.get_section_video_bottom_margin(group=group),
        }

    def layout_groups_static(self) -> None:
        if not self.group_entries:
            return

        view_width = self.scene.sceneRect().width()
        view_height = self.scene.sceneRect().height()

        total_stack_height = sum(group_entry["group_total_height"] for group_entry in self.group_entries)
        for group_entry in self.group_entries[:-1]:
            total_stack_height += group_entry["group_gap"]

        bottom_margin = self.group_entries[-1]["bottom_margin"]
        current_y = view_height - bottom_margin - total_stack_height

        for group_index, group_entry in enumerate(self.group_entries):
            for section_index, section_entry in enumerate(group_entry["section_entries"]):
                content_width = section_entry["reserved_content_width"]
                content_height = section_entry["reserved_content_height"]
                padding_x = section_entry["padding_x"]
                padding_y = section_entry["padding_y"]

                bg_width = content_width + (padding_x * 2)
                bg_height = content_height + (padding_y * 2)

                bg_x = (view_width - bg_width) / 2.0
                bg_y = current_y

                section_entry["background_item"].setRect(QRectF(bg_x, bg_y, bg_width, bg_height))

                content_x = bg_x + padding_x
                content_y = bg_y + padding_y

                for slot in section_entry["slot_layout"]:
                    item = slot["item"]
                    item_x = content_x + slot["slot_x"] + slot["base_x_in_slot"]
                    item_y = content_y + slot["slot_y"] + slot["base_y_in_slot"]
                    item.setPos(item_x, item_y)

                current_y += bg_height
                if section_index < len(group_entry["section_entries"]) - 1:
                    current_y += section_entry["section_gap"]

            if group_index < len(self.group_entries) - 1:
                current_y += group_entry["group_gap"]

    def build_groups(self, groups: list[dict]) -> None:
        self.clear()
        self.current_group_set = tuple(id(g) for g in groups)

        scene_rect = self.scene.sceneRect()
        self.current_scene_size = (scene_rect.width(), scene_rect.height())

        self.group_entries = [self.build_group_entry(group) for group in groups]
        self.layout_groups_static()

    def resolve_scale_factor(self, resolved_animations: list[dict], progress: float) -> float:
        scale_factor = 1.0

        for animation in resolved_animations:
            animation_type = animation.get("type")

            if animation_type == "scale":
                target_scale = max(0.01, float(animation.get("scale", 1.25)))
                cycles = max(1.0, float(animation.get("cycles", 1)))

                cycle_progress = (progress * cycles) % 1.0
                pulse_t = 1.0 - abs((cycle_progress * 2.0) - 1.0)
                eased_pulse = ease_in_out_cubic(pulse_t)

                scale_factor *= 1.0 + ((target_scale - 1.0) * eased_pulse)

            elif animation_type == "pop":
                target_scale = max(0.01, float(animation.get("scale", 1.25)))
                cycles = max(1.0, float(animation.get("cycles", 1)))
                attack_portion = 0.18

                cycle_progress = (progress * cycles) % 1.0

                if progress <= 0.0 or progress >= 1.0:
                    pop_amount = 0.0
                elif cycle_progress < attack_portion:
                    pop_amount = ease_in_out_cubic(cycle_progress / attack_portion)
                else:
                    decay_t = (cycle_progress - attack_portion) / max(0.001, 1.0 - attack_portion)
                    pop_amount = 1.0 - ease_in_out_cubic(decay_t)

                scale_factor *= 1.0 + ((target_scale - 1.0) * pop_amount)

        return scale_factor

    def resolve_vertical_offset(self, resolved_animations: list[dict], progress: float) -> float:
        offset_y = 0.0

        for animation in resolved_animations:
            if animation.get("type") == "bounce":
                amplitude_px = max(0.0, float(animation.get("amplitude_px", 8)))
                cycles = max(0.0, float(animation.get("cycles", 2)))
                direction = animation.get("direction", "up")

                if amplitude_px <= 0.0 or cycles <= 0.0:
                    continue

                pulse_t = 1.0 - abs((progress * 2.0) - 1.0)
                eased_envelope = ease_in_out_cubic(pulse_t)

                if direction == "up":
                    oscillation = -abs(math.sin(progress * cycles * math.pi))
                elif direction == "down":
                    oscillation = abs(math.sin(progress * cycles * math.pi))
                else:
                    oscillation = math.sin(progress * cycles * 2.0 * math.pi)

                offset_y += amplitude_px * eased_envelope * oscillation

        return offset_y

    def resolve_rotation_deg(self, resolved_animations: list[dict], progress: float) -> float:
        rotation_deg = 0.0

        for animation in resolved_animations:
            if animation.get("type") == "jiggle":
                angle_deg = max(0.0, abs(float(animation.get("angle_deg", 5))))
                cycles = max(0.0, float(animation.get("cycles", 3)))

                if angle_deg <= 0.0 or cycles <= 0.0:
                    continue

                pulse_t = 1.0 - abs((progress * 2.0) - 1.0)
                eased_envelope = ease_in_out_cubic(pulse_t)
                oscillation = math.sin(progress * cycles * 2.0 * math.pi)

                rotation_deg += angle_deg * eased_envelope * oscillation

        return rotation_deg

    def apply_item_animation_state(
        self,
        item: WordGraphicsItem,
        owner: dict,
        resolved_animations: list[dict],
        group: dict,
        section: dict,
        time_seconds: float,
    ) -> None:
        is_word = owner in section.get("words", [])
        progress = self.caption_model.compute_owner_effective_progress(
            owner,
            time_seconds,
            group=group,
            section=section,
            word=owner if is_word else None,
            resolved_animations=resolved_animations,
        )

        item.set_reveal_progress(progress)
        item.set_scale_factor(self.resolve_scale_factor(resolved_animations, progress))
        item.set_offset_y(self.resolve_vertical_offset(resolved_animations, progress))
        item.set_rotation_deg(self.resolve_rotation_deg(resolved_animations, progress))

    def update_group_items(self, time_seconds: float) -> None:
        if self.caption_model is None or not self.group_entries:
            return

        for group_index, group_entry in enumerate(self.group_entries):
            for section_entry in group_entry["section_entries"]:
                background_rect = section_entry["background_item"].rect()
                group = section_entry["group"]
                section = section_entry["section"]
                padding_x = section_entry["padding_x"]
                padding_y = section_entry["padding_y"]

                base_z = 20 + (group_index * 20)
                section_entry["background_item"].setZValue(base_z)

                for slot in section_entry["slot_layout"]:
                    item = slot["item"]
                    owner = slot["owner"]
                    resolved_animations = slot["resolved_animations"]

                    self.apply_item_animation_state(item, owner, resolved_animations, group, section, time_seconds)

                    static_x = background_rect.x() + padding_x + slot["slot_x"] + slot["base_x_in_slot"]
                    static_y = background_rect.y() + padding_y + slot["slot_y"] + slot["base_y_in_slot"]

                    item.setPos(static_x, static_y + item.offset_y)
                    item.setZValue(base_z + 1)

    def render(self, time_seconds: float) -> None:
        if self.caption_model is None:
            return

        active_groups = self.caption_model.get_active_groups(time_seconds)
        scene_rect = self.scene.sceneRect()
        scene_size = (scene_rect.width(), scene_rect.height())
        group_set = tuple(id(g) for g in active_groups)

        if not active_groups:
            if self.group_entries:
                self.clear()
            return

        if self.current_group_set != group_set or self.current_scene_size != scene_size:
            self.build_groups(active_groups)

        self.update_group_items(time_seconds)