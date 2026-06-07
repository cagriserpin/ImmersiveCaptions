
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


class FaceIdentityStore:
    def __init__(self, json_path: str | Path | None = None) -> None:
        self.json_path = Path(json_path) if json_path else None
        self.identities_by_id: dict[int, dict] = {}
        self.detection_to_identity: dict[str, int] = {}

        if self.json_path is not None:
            self.load(self.json_path)

    def clear(self) -> None:
        self.identities_by_id.clear()
        self.detection_to_identity.clear()
        self.json_path = None

    def load(self, json_path: str | Path) -> None:
        self.json_path = Path(json_path)
        with open(self.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.identities_by_id = {}
        for identity in data.get("identities", []):
            try:
                identity_id = int(identity.get("identity_id", -1))
            except Exception:
                continue
            if identity_id >= 0:
                self.identities_by_id[identity_id] = identity

        raw_mapping = data.get("detection_to_identity", {})
        self.detection_to_identity = {}
        if isinstance(raw_mapping, dict):
            for key, value in raw_mapping.items():
                try:
                    self.detection_to_identity[str(key)] = int(value)
                except Exception:
                    continue

    def is_loaded(self) -> bool:
        return bool(self.identities_by_id)

    def get_identity_for_detection(self, detection_id) -> dict | None:
        if detection_id is None:
            return None

        identity_id = self.detection_to_identity.get(str(detection_id))
        if identity_id is None:
            return None

        identity = self.identities_by_id.get(identity_id)
        if identity is None:
            return None

        return identity

    def get_display_name_for_detection(self, detection_id) -> str | None:
        identity = self.get_identity_for_detection(detection_id)
        if identity is None:
            return None

        identity_id = int(identity.get("identity_id", -1))
        status = str(identity.get("status", "candidate")).strip().lower()
        manual_name = str(identity.get("manual_name", "")).strip()

        if status == "ignore":
            return ""
        if manual_name:
            return manual_name
        if identity_id >= 0:
            return f"id {identity_id}"
        return None

    def get_label_for_detection(self, detection_id) -> str | None:
        return self.get_display_name_for_detection(detection_id)

    def get_manual_name_for_detection(self, detection_id) -> str | None:
        identity = self.get_identity_for_detection(detection_id)
        if identity is None:
            return None

        status = str(identity.get("status", "candidate")).strip().lower()
        if status == "ignore":
            return ""
        manual_name = str(identity.get("manual_name", "")).strip()
        return manual_name or None


class TranscriptStore:
    def __init__(self, json_path: str | Path | None = None) -> None:
        self.json_path = Path(json_path) if json_path else None
        self.entries: list[dict] = []
        self.group_times: list[float] = []
        self.groups_by_time: dict[float, list[dict]] = {}

        if self.json_path is not None:
            self.load(self.json_path)

    def clear(self) -> None:
        self.json_path = None
        self.entries = []
        self.group_times = []
        self.groups_by_time = {}

    def load(self, json_path: str | Path) -> None:
        self.json_path = Path(json_path)
        with open(self.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        raw_entries = data.get("entries", [])
        self.entries = []
        if isinstance(raw_entries, list):
            for entry in raw_entries:
                if not isinstance(entry, dict):
                    continue
                try:
                    time_value = float(entry.get("time", 0.0))
                except Exception:
                    continue
                normalized = dict(entry)
                normalized["time"] = time_value
                normalized["type"] = str(entry.get("type", "dialogue")).strip().lower() or "dialogue"
                normalized["name"] = str(entry.get("name", "")).strip()
                normalized["text"] = str(entry.get("text", "")).strip()
                self.entries.append(normalized)

        self.entries.sort(key=lambda item: (float(item.get("time", 0.0)), int(item.get("id", 0))))
        self.groups_by_time = {}
        for entry in self.entries:
            self.groups_by_time.setdefault(float(entry["time"]), []).append(entry)
        self.group_times = sorted(self.groups_by_time.keys())

    def is_loaded(self) -> bool:
        return bool(self.entries)

    def get_active_entries(self, time_seconds: float) -> list[dict]:
        if not self.group_times:
            return []

        idx = bisect_right(self.group_times, float(time_seconds)) - 1
        if idx < 0:
            return []

        active_time = self.group_times[idx]
        return list(self.groups_by_time.get(active_time, []))
