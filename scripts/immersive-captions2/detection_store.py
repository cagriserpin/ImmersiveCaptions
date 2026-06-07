from __future__ import annotations

from bisect import bisect_right
from pathlib import Path
import json


class FaceDetectionStore:
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
        self.metadata = {
            "video_path": data.get("video_path"),
            "fps": data.get("fps"),
            "width": data.get("width"),
            "height": data.get("height"),
            "detector": data.get("detector"),
            "frame_count": data.get("frame_count"),
        }

    def is_loaded(self) -> bool:
        return bool(self.frames)

    def get_frame(self, time_seconds: float) -> dict | None:
        if not self.frames:
            return None
        idx = bisect_right(self.times, time_seconds) - 1
        if idx < 0:
            idx = 0
        if idx >= len(self.frames):
            idx = len(self.frames) - 1
        return self.frames[idx]

    def get_faces(self, time_seconds: float) -> list[dict]:
        frame = self.get_frame(time_seconds)
        if frame is None:
            return []
        faces = frame.get("faces", [])
        return faces if isinstance(faces, list) else []
