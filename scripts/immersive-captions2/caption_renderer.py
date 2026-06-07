
from __future__ import annotations

from bisect import bisect_right
from pathlib import Path
import json

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QPen
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsSimpleTextItem

from caption_model import CaptionModel

FACE_CAPTION_MARGIN = 12.0
FALLBACK_BOTTOM_MARGIN = 110.0
CAPTION_SCREEN_PADDING = 10.0


class FaceTrackStore:
    def __init__(self, json_path: str | Path | None = None) -> None:
        self.json_path = Path(json_path) if json_path else None
        self.frames: list[dict] = []
        self.times: list[float] = []
        self.metadata: dict = {}

        if self.json_path is not None:
            self.load(self.json_path)

    def load(self, json_path: str | Path) -> None:
        self.json_path = Path(json_path)
        with open(self.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        frames = data.get("frames", [])
        self.frames = frames if isinstance(frames, list) else []
        self.times = [float(frame.get("time_seconds", 0.0)) for frame in self.frames]
        self.metadata = data if isinstance(data, dict) else {}

    def get_frame(self, time_seconds: float) -> dict | None:
        if not self.frames:
            return None
        idx = bisect_right(self.times, time_seconds) - 1
        if idx < 0:
            idx = 0
        if idx >= len(self.frames):
            idx = len(self.frames) - 1
        return self.frames[idx]

    def get_track_bbox(self, track_id: int, time_seconds: float) -> tuple[int, int, int, int] | None:
        frame = self.get_frame(time_seconds)
        if frame is None:
            return None
        for detection in frame.get("detections", []):
            if int(detection.get("track_id", -1)) == int(track_id):
                bbox = detection.get("bbox", [])
                if isinstance(bbox, list) and len(bbox) == 4:
                    return tuple(int(v) for v in bbox)
        return None

    def get_all_bboxes(self, time_seconds: float) -> list[tuple[int, tuple[int, int, int, int]]]:
        frame = self.get_frame(time_seconds)
        if frame is None:
            return []
        result = []
        for detection in frame.get("detections", []):
            bbox = detection.get("bbox", [])
            if isinstance(bbox, list) and len(bbox) == 4:
                result.append((int(detection.get("track_id", -1)), tuple(int(v) for v in bbox)))
        return result


class CaptionRenderer:
    def __init__(self, scene, caption_model: CaptionModel | None = None):
        self.scene = scene
        self.caption_model = caption_model
        self.face_tracks: FaceTrackStore | None = None

        self.caption_items = []
        self.debug_items = []
        self.show_debug_faces = True

    def set_face_tracks(self, json_path: str | Path | None) -> None:
        if json_path is None:
            self.face_tracks = None
            return
        self.face_tracks = FaceTrackStore(json_path)

    def clear(self) -> None:
        for item in self.caption_items:
            self.scene.removeItem(item)
        for item in self.debug_items:
            self.scene.removeItem(item)
        self.caption_items.clear()
        self.debug_items.clear()

    def _make_font(self, family: str, size: int, weight: int) -> QFont:
        font = QFont(family)
        font.setPointSize(int(size))
        font.setWeight(int(weight))
        return font

    def _add_face_debug(self, time_seconds: float) -> None:
        if not self.show_debug_faces or self.face_tracks is None:
            return

        for track_id, bbox in self.face_tracks.get_all_bboxes(time_seconds):
            x, y, w, h = bbox
            rect_item = QGraphicsRectItem(QRectF(x, y, w, h))
            rect_item.setPen(QPen(QColor(80, 220, 255, 220), 2))
            rect_item.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            rect_item.setZValue(50)
            self.scene.addItem(rect_item)
            self.debug_items.append(rect_item)

            label = QGraphicsSimpleTextItem(f"track {track_id}")
            label.setBrush(QBrush(QColor(80, 220, 255)))
            label.setPos(x, max(0.0, y - 22.0))
            label.setZValue(51)
            self.scene.addItem(label)
            self.debug_items.append(label)

    def _section_text(self, section: dict) -> str:
        if section.get("type") == "dialogue":
            return " ".join(word.get("text", "") for word in section.get("words", []))
        if section.get("type") == "sfx":
            return str(section.get("text", ""))
        return ""

    def _dialogue_top_position(self, section: dict, time_seconds: float, text_width: float, text_height: float) -> tuple[float, float]:
        scene_rect = self.scene.sceneRect()
        fallback_x = (scene_rect.width() - text_width) / 2.0
        fallback_y = max(CAPTION_SCREEN_PADDING, scene_rect.height() - FALLBACK_BOTTOM_MARGIN - text_height)

        if self.caption_model is None or self.face_tracks is None:
            return fallback_x, fallback_y

        speaker = section.get("speaker")
        track_id = self.caption_model.get_speaker_track_id(speaker)
        if track_id is None:
            return fallback_x, fallback_y

        bbox = self.face_tracks.get_track_bbox(track_id, time_seconds)
        if bbox is None:
            return fallback_x, fallback_y

        x, y, w, h = bbox
        text_x = (x + (w / 2.0)) - (text_width / 2.0)
        text_y = y + h + FACE_CAPTION_MARGIN

        max_x = max(CAPTION_SCREEN_PADDING, scene_rect.width() - text_width - CAPTION_SCREEN_PADDING)
        max_y = max(CAPTION_SCREEN_PADDING, scene_rect.height() - text_height - CAPTION_SCREEN_PADDING)
        text_x = min(max(text_x, CAPTION_SCREEN_PADDING), max_x)
        text_y = min(max(text_y, CAPTION_SCREEN_PADDING), max_y)
        return text_x, text_y

    def _draw_section(self, section: dict, time_seconds: float) -> None:
        if self.caption_model is None:
            return

        defaults = self.caption_model.get_defaults()
        speaker = section.get("speaker")
        style = self.caption_model.get_speaker_style(speaker)

        family = str(style.get("font", defaults.get("font", "Calibri")))
        size = int(style.get("font_size", defaults.get("font_size", 28)))
        weight = int(style.get("font_weight", defaults.get("font_weight", 400)))
        color = QColor(str(style.get("font_color", defaults.get("font_color", "#ffffff"))))

        text = self._section_text(section)
        if not text:
            return

        font = self._make_font(family, size, weight)
        metrics = QFontMetricsF(font)
        width = metrics.horizontalAdvance(text)
        height = metrics.height()

        if section.get("type") == "dialogue":
            text_x, text_y = self._dialogue_top_position(section, time_seconds, width, height)
        else:
            scene_rect = self.scene.sceneRect()
            text_x = (scene_rect.width() - width) / 2.0
            text_y = max(CAPTION_SCREEN_PADDING, scene_rect.height() - FALLBACK_BOTTOM_MARGIN - height)

        bg = QGraphicsRectItem(QRectF(text_x - 10, text_y - 6, width + 20, height + 12))
        bg.setBrush(QBrush(QColor(0, 0, 0, 170)))
        bg.setPen(QPen(Qt.PenStyle.NoPen))
        bg.setZValue(100)
        self.scene.addItem(bg)
        self.caption_items.append(bg)

        item = QGraphicsSimpleTextItem(text)
        item.setFont(font)
        item.setBrush(QBrush(color))
        item.setPos(text_x, text_y)
        item.setZValue(101)
        self.scene.addItem(item)
        self.caption_items.append(item)

    def render(self, time_seconds: float) -> None:
        self.clear()
        if self.caption_model is None:
            return

        self._add_face_debug(time_seconds)

        active_sections = self.caption_model.get_active_sections(time_seconds)
        for section in active_sections:
            self._draw_section(section, time_seconds)
