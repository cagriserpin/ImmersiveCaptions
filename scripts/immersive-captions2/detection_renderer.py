from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsRectItem, QGraphicsSimpleTextItem


class DetectionRenderer:
    def __init__(self, scene) -> None:
        self.scene = scene
        self.items = []
        self.show_boxes = True
        self.show_landmarks = True
        self.show_scores = True

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
        label.setBrush(QBrush(color))
        label.setPos(x, max(0.0, y - 22.0))
        label.setZValue(52)
        self.scene.addItem(label)
        self.items.append(label)

    def render_faces(self, faces: list[dict]) -> None:
        self.clear()

        if not faces:
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
                detection_id = face.get("detection_id", "?")
                score = face.get("score")
                if isinstance(score, (float, int)):
                    label_text = f"id {detection_id}  {float(score):.2f}"
                else:
                    label_text = f"id {detection_id}"
                self._add_label(x, y, label_text, box_color)
