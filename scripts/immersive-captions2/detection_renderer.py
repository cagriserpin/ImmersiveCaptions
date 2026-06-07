
from __future__ import annotations

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

    def set_identity_store(self, identity_store: FaceIdentityStore | None) -> None:
        self.identity_store = identity_store

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

    def _add_caption(self, anchor_x: float, anchor_y: float, text: str, bg_color: QColor | None = None) -> None:
        text = text.strip()
        if not text:
            return

        item = QGraphicsSimpleTextItem(text)
        font = QFont("Arial", 14)
        font.setWeight(QFont.Weight.Bold)
        item.setFont(font)
        item.setBrush(QBrush(QColor(255, 255, 255)))

        metrics = QFontMetricsF(font)
        width = metrics.horizontalAdvance(text)
        height = metrics.height()

        item_x = anchor_x - (width / 2.0)
        item_y = anchor_y - height

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

    def _render_dialogue_captions(self, faces: list[dict], captions: list[dict]) -> None:
        if self.identity_store is None or not self.identity_store.is_loaded():
            return

        faces_by_name: dict[str, list[dict]] = {}
        for face in faces:
            manual_name = self._get_manual_name_for_face(face)
            if not manual_name:
                continue
            faces_by_name.setdefault(manual_name, []).append(face)

        stacked_offsets: dict[str, int] = {}
        for caption in captions:
            if str(caption.get("type", "dialogue")).strip().lower() != "dialogue":
                continue

            name = str(caption.get("name", "")).strip()
            text = str(caption.get("text", "")).strip()
            if not name or not text:
                continue

            matched_faces = faces_by_name.get(name, [])
            if not matched_faces:
                continue

            for face in matched_faces:
                bbox = face.get("bbox", [])
                if not isinstance(bbox, list) or len(bbox) != 4:
                    continue
                x, y, w, h = [float(v) for v in bbox]

                stack_key = f"{name}:{int(face.get('detection_id', -1))}"
                offset_index = stacked_offsets.get(stack_key, 0)
                stacked_offsets[stack_key] = offset_index + 1

                anchor_x = x + (w / 2.0)
                anchor_y = max(24.0, y - 10.0 - (offset_index * 30.0))
                self._add_caption(anchor_x, anchor_y, text)

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

    def render_faces(self, faces: list[dict], captions: list[dict] | None = None) -> None:
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
            self._render_dialogue_captions(faces, captions)
            self._render_sfx_captions(captions)
