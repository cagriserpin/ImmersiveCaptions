from __future__ import annotations

from math import hypot

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QPen
from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsRectItem, QGraphicsSimpleTextItem

from detection_store import FaceIdentityStore


class DetectionRenderer:
    def __init__(self, scene) -> None:
        self.scene = scene
        self.items = []
        self.show_boxes = True
        self.show_landmarks = True
        self.show_scores = True
        self.identity_store: FaceIdentityStore | None = None

        self.caption_stack_spacing = 30.0
        self.caption_anchor_margin_y = 16.0
        self.caption_hold_seconds = 0.5
        self.caption_dead_zone_px = 5.0
        self.caption_snap_distance_px = 200.0
        self.caption_smooth_alpha_small = 0.1
        self.caption_smooth_alpha_medium = 0.2

        self.caption_anchor_states: dict[str, dict[str, float]] = {}
        self.last_render_time: float | None = None

    def set_identity_store(self, identity_store: FaceIdentityStore | None) -> None:
        self.identity_store = identity_store
        self.reset_caption_tracking()

    def reset_caption_tracking(self) -> None:
        self.caption_anchor_states.clear()
        self.last_render_time = None

    def clear(self) -> None:
        for item in self.items:
            self.scene.removeItem(item)
        self.items.clear()

    def _add_rect(self, x: float, y: float, w: float, h: float, color: QColor, width: float = 2.0) -> None:
        rect_item = QGraphicsRectItem(QRectF(x, y, w, h))
        rect_item.setPen(QPen(color, width))
        rect_item.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        rect_item.setZValue(50)
        self.scene.addItem(rect_item)
        self.items.append(rect_item)

    def _add_landmark(self, x: float, y: float, color: QColor) -> None:
        radius = 2.5
        item = QGraphicsEllipseItem(QRectF(x - radius, y - radius, radius * 2.0, radius * 2.0))
        item.setPen(QPen(Qt.PenStyle.NoPen))
        item.setBrush(QBrush(color))
        item.setZValue(51)
        self.scene.addItem(item)
        self.items.append(item)

    def _add_label(self, x: float, y: float, text: str, color: QColor) -> None:
        label = QGraphicsSimpleTextItem(text)
        font = QFont("Arial", 11)
        font.setWeight(QFont.Weight.Bold)
        label.setFont(font)
        label.setBrush(QBrush(QColor(255, 255, 255)))
        label.setPos(x + 6.0, max(0.0, y - 24.0))
        label.setZValue(53)
        self.scene.addItem(label)
        self.items.append(label)

        bg = QGraphicsRectItem(label.boundingRect().adjusted(-6.0, -3.0, 6.0, 3.0))
        bg.setPos(label.pos())
        bg.setPen(QPen(Qt.PenStyle.NoPen))
        bg.setBrush(QBrush(QColor(0, 0, 0, 180)))
        bg.setZValue(52)
        self.scene.addItem(bg)
        self.items.append(bg)

    def _add_caption(self, center_x: float, top_y: float, text: str, bg_color: QColor | None = None) -> None:
        text = text.strip()
        if not text:
            return

        item = QGraphicsSimpleTextItem(text)
        font = QFont("Arial", 14)
        font.setWeight(QFont.Weight.Bold)
        item.setFont(font)
        item.setBrush(QBrush(QColor(255, 255, 255)))

        bounds = item.boundingRect()
        width = bounds.width()
        height = bounds.height()

        scene_rect = self.scene.sceneRect()
        padding = 8.0
        item_x = center_x - (width / 2.0)
        item_y = top_y

        max_x = max(padding, scene_rect.width() - width - padding)
        max_y = max(padding, scene_rect.height() - height - padding)
        item_x = min(max(item_x, padding), max_x)
        item_y = min(max(item_y, padding), max_y)

        bg_rect = QGraphicsRectItem(QRectF(item_x - 8.0, item_y - 4.0, width + 16.0, height + 8.0))
        bg_rect.setPen(QPen(Qt.PenStyle.NoPen))
        bg_rect.setBrush(QBrush(bg_color or QColor(0, 0, 0, 185)))
        bg_rect.setZValue(59)
        self.scene.addItem(bg_rect)
        self.items.append(bg_rect)

        item.setPos(item_x, item_y)
        item.setZValue(60)
        self.scene.addItem(item)
        self.items.append(item)

    def _build_label_text(self, face: dict) -> str | None:
        detection_id = face.get("detection_id")
        score = face.get("score")

        if self.identity_store is not None and self.identity_store.is_loaded():
            name = self.identity_store.get_label_for_detection(detection_id)
            if name == "":
                return None
            if name:
                if isinstance(score, (float, int)):
                    return f"{name}  {float(score):.2f}"
                return name

        if detection_id is None:
            return None

        if isinstance(score, (float, int)):
            return f"id {detection_id}  {float(score):.2f}"
        return f"id {detection_id}"

    def _get_manual_name_for_face(self, face: dict) -> str | None:
        if self.identity_store is None or not self.identity_store.is_loaded():
            return None
        return self.identity_store.get_manual_name_for_detection(face.get("detection_id"))

    def _raw_anchor_for_face(self, face: dict) -> tuple[float, float] | None:
        bbox = face.get("bbox", [])
        if not isinstance(bbox, list) or len(bbox) != 4:
            return None
        x, y, w, h = [float(v) for v in bbox]
        return (x + (w / 2.0), y + h + self.caption_anchor_margin_y)

    def _smooth_anchor(self, key: str, raw_x: float, raw_y: float, current_time: float) -> tuple[float, float]:
        state = self.caption_anchor_states.get(key)
        if state is None:
            self.caption_anchor_states[key] = {"x": raw_x, "y": raw_y, "last_seen": current_time}
            return raw_x, raw_y

        prev_x = float(state["x"])
        prev_y = float(state["y"])
        distance = hypot(raw_x - prev_x, raw_y - prev_y)

        if distance <= self.caption_dead_zone_px:
            new_x, new_y = prev_x, prev_y
        elif distance >= self.caption_snap_distance_px:
            new_x, new_y = raw_x, raw_y
        else:
            alpha = self.caption_smooth_alpha_small if distance < 18.0 else self.caption_smooth_alpha_medium
            new_x = prev_x + ((raw_x - prev_x) * alpha)
            new_y = prev_y + ((raw_y - prev_y) * alpha)

        state["x"] = new_x
        state["y"] = new_y
        state["last_seen"] = current_time
        return new_x, new_y

    def _prune_anchor_states(self, current_time: float, active_names: set[str]) -> None:
        stale_keys = []
        for key, state in self.caption_anchor_states.items():
            if key in active_names:
                continue
            last_seen = float(state.get("last_seen", current_time))
            if (current_time - last_seen) > self.caption_hold_seconds:
                stale_keys.append(key)
        for key in stale_keys:
            self.caption_anchor_states.pop(key, None)

    def _render_dialogue_captions(self, faces: list[dict], captions: list[dict], current_time: float) -> None:
        if self.identity_store is None or not self.identity_store.is_loaded():
            return

        anchors_by_name: dict[str, tuple[float, float]] = {}
        for face in faces:
            manual_name = self._get_manual_name_for_face(face)
            if not manual_name:
                continue
            raw_anchor = self._raw_anchor_for_face(face)
            if raw_anchor is None:
                continue
            anchors_by_name[manual_name] = self._smooth_anchor(
                manual_name,
                raw_anchor[0],
                raw_anchor[1],
                current_time,
            )

        captions_by_name: dict[str, list[dict]] = {}
        active_names: set[str] = set()
        for caption in captions:
            if str(caption.get("type", "dialogue")).strip().lower() != "dialogue":
                continue
            name = str(caption.get("name", "")).strip()
            text = str(caption.get("text", "")).strip()
            if not name or not text:
                continue
            captions_by_name.setdefault(name, []).append(caption)
            active_names.add(name)

        self._prune_anchor_states(current_time, active_names)

        for name, name_captions in captions_by_name.items():
            sorted_captions = sorted(
                name_captions,
                key=lambda item: (float(item.get("time", 0.0)), int(item.get("id", 0))),
            )

            anchor = anchors_by_name.get(name)
            if anchor is None:
                # If the face is temporarily lost, keep the caption at the last known
                # location for as long as the caption itself is still active.
                state = self.caption_anchor_states.get(name)
                if state is not None:
                    anchor = (float(state["x"]), float(state["y"]))
                else:
                    continue

            base_x, base_y = anchor
            for idx, caption in enumerate(sorted_captions):
                top_y = base_y + (idx * self.caption_stack_spacing)
                self._add_caption(base_x, top_y, str(caption.get("text", "")))

    def _render_sfx_captions(self, captions: list[dict]) -> None:
        for caption in captions:
            if str(caption.get("type", "dialogue")).strip().lower() != "sfx":
                continue

            text = str(caption.get("text", "")).strip()
            if not text:
                continue

            x = caption.get("x")
            y = caption.get("y")
            if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                continue

            self._add_caption(float(x), float(y), text, bg_color=QColor(25, 25, 25, 205))

    def render_faces(self, faces: list[dict], captions: list[dict] | None = None, current_time: float = 0.0) -> None:
        if self.last_render_time is not None and abs(current_time - self.last_render_time) > 0.35:
            self.reset_caption_tracking()
        self.last_render_time = current_time

        self.clear()

        if not faces and not captions:
            return

        box_color = QColor(80, 220, 255, 230)
        landmark_color = QColor(255, 190, 80, 240)

        for face in faces:
            bbox = face.get("bbox", [])
            if not isinstance(bbox, list) or len(bbox) != 4:
                continue

            x, y, w, h = [float(v) for v in bbox]

            if self.show_boxes:
                self._add_rect(x, y, w, h, box_color)

            if self.show_landmarks:
                landmarks = face.get("landmarks", [])
                if isinstance(landmarks, list):
                    for point in landmarks:
                        if isinstance(point, list) and len(point) == 2:
                            self._add_landmark(float(point[0]), float(point[1]), landmark_color)

            if self.show_scores:
                label_text = self._build_label_text(face)
                if label_text:
                    self._add_label(x, y, label_text, box_color)

        if captions:
            self._render_dialogue_captions(faces, captions, current_time)
            self._render_sfx_captions(captions)
