
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

        if self.json_path is not None:
            self.load(self.json_path)

    def clear(self) -> None:
        self.json_path = None
        self.entries = []

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
                    start_time = float(entry.get("time", 0.0))
                except Exception:
                    continue

                normalized = dict(entry)
                normalized["time"] = start_time
                normalized["type"] = str(entry.get("type", "dialogue")).strip().lower() or "dialogue"
                normalized["name"] = str(entry.get("name", "")).strip()
                normalized["text"] = str(entry.get("text", "")).strip()

                explicit_end = entry.get("end_time")
                if isinstance(explicit_end, (int, float)):
                    normalized["end_time"] = float(explicit_end)
                else:
                    try:
                        normalized["end_time"] = float(explicit_end)
                    except Exception:
                        normalized["end_time"] = None

                self.entries.append(normalized)

        self.entries.sort(key=lambda item: (float(item.get("time", 0.0)), int(item.get("id", 0))))
        self._apply_default_end_times()

    def _estimate_duration(self, entry: dict) -> float:
        text = str(entry.get("text", "")).replace("\n", " ").strip()
        text_len = len(text)

        # Slightly longer timings for readability.
        if str(entry.get("type", "dialogue")) == "sfx":
            base = 1.9
            chars_per_second = 15.0
            min_dur = 1.8
            max_dur = 4.8
        else:
            base = 1.6
            chars_per_second = 17.0
            min_dur = 1.5
            max_dur = 4.2

        duration = base + (text_len / chars_per_second)
        return max(min_dur, min(max_dur, duration))

    def _apply_default_end_times(self) -> None:
        # Independent caption lifetime per entry.
        next_by_name: dict[str, list[float]] = {}
        for entry in self.entries:
            name = str(entry.get("name", "")).strip()
            if not name:
                continue
            next_by_name.setdefault(name, []).append(float(entry["time"]))

        # Precompute next same-speaker time after each entry.
        for idx, entry in enumerate(self.entries):
            start_time = float(entry["time"])
            end_time = entry.get("end_time")
            if isinstance(end_time, (int, float)) and float(end_time) > start_time:
                entry["end_time"] = float(end_time)
                continue

            target_end = start_time + self._estimate_duration(entry)

            name = str(entry.get("name", "")).strip()
            if name:
                same_name_future = [
                    float(other["time"])
                    for j, other in enumerate(self.entries)
                    if j > idx and str(other.get("name", "")).strip() == name and float(other["time"]) > start_time
                ]
                if same_name_future:
                    next_same_name = min(same_name_future)
                    target_end = min(target_end, max(start_time + 0.45, next_same_name - 0.05))

            entry["end_time"] = round(float(target_end), 3)

    def is_loaded(self) -> bool:
        return bool(self.entries)

    def get_active_entries(self, time_seconds: float) -> list[dict]:
        current = float(time_seconds)
        active = []
        for entry in self.entries:
            start_time = float(entry.get("time", 0.0))
            end_time = float(entry.get("end_time", start_time))
            if start_time <= current < end_time:
                active.append(entry)
        active.sort(key=lambda item: (float(item.get("time", 0.0)), int(item.get("id", 0))))
        return active

