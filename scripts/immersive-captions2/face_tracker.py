from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import cv2


@dataclass
class TrackState:
    track_id: int
    bbox: tuple[int, int, int, int]
    miss_count: int = 0

    @property
    def center(self) -> tuple[float, float]:
        x, y, w, h = self.bbox
        return x + (w / 2.0), y + (h / 2.0)


class FaceTracker:
    def __init__(self, distance_threshold: float = 90.0, max_missed_frames: int = 12) -> None:
        self.distance_threshold = float(distance_threshold)
        self.max_missed_frames = int(max_missed_frames)
        self._next_track_id = 0
        self._tracks: list[TrackState] = []

        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.face_cascade = cv2.CascadeClassifier(cascade_path)

    def _distance(self, a: tuple[float, float], b: tuple[float, float]) -> float:
        dx = a[0] - b[0]
        dy = a[1] - b[1]
        return (dx * dx + dy * dy) ** 0.5

    def _create_track(self, bbox: tuple[int, int, int, int]) -> TrackState:
        track = TrackState(track_id=self._next_track_id, bbox=bbox)
        self._next_track_id += 1
        self._tracks.append(track)
        return track

    def update(self, detections: list[tuple[int, int, int, int]]) -> list[TrackState]:
        assigned_tracks: list[TrackState] = []
        used_ids: set[int] = set()

        for bbox in detections:
            x, y, w, h = bbox
            center = (x + (w / 2.0), y + (h / 2.0))

            best_track: TrackState | None = None
            best_distance = self.distance_threshold

            for track in self._tracks:
                if track.track_id in used_ids:
                    continue
                distance = self._distance(center, track.center)
                if distance < best_distance:
                    best_distance = distance
                    best_track = track

            if best_track is None:
                best_track = self._create_track(bbox)
            else:
                best_track.bbox = bbox
                best_track.miss_count = 0

            used_ids.add(best_track.track_id)
            assigned_tracks.append(best_track)

        still_active: list[TrackState] = []
        for track in self._tracks:
            if track.track_id not in used_ids:
                track.miss_count += 1
            if track.miss_count <= self.max_missed_frames:
                still_active.append(track)

        self._tracks = still_active
        return assigned_tracks

    def detect_faces(self, frame) -> list[tuple[int, int, int, int]]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(36, 36),
        )
        return [tuple(int(v) for v in face) for face in faces]


def process_video_faces(
    video_path: str | Path,
    output_json_path: str | Path,
    sample_every_n_frames: int = 2,
) -> dict:
    video_path = str(video_path)
    output_json_path = str(output_json_path)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

    tracker = FaceTracker()
    frames: list[dict] = []
    frame_index = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        if frame_index % max(1, sample_every_n_frames) == 0:
            detections = tracker.detect_faces(frame)
            tracks = tracker.update(detections)
            frames.append(
                {
                    "frame_index": frame_index,
                    "time_seconds": frame_index / fps,
                    "detections": [
                        {
                            "track_id": track.track_id,
                            "bbox": list(track.bbox),
                        }
                        for track in tracks
                    ],
                }
            )

        frame_index += 1

    cap.release()

    result = {
        "video_path": video_path,
        "fps": fps,
        "width": width,
        "height": height,
        "sample_every_n_frames": sample_every_n_frames,
        "frames": frames,
    }

    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result
