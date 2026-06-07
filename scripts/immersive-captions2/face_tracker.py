from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import cv2


YUNET_URLS = [
    "https://huggingface.co/opencv/face_detection_yunet/resolve/main/face_detection_yunet_2023mar.onnx",
    "https://files.kde.org/digikam/facesengine/yunet/face_detection_yunet_2023mar.onnx",
]


@dataclass
class FaceDetection:
    detection_id: int
    bbox: tuple[int, int, int, int]
    score: float
    landmarks: list[tuple[float, float]]
    crop_path: str

    def to_dict(self) -> dict:
        return {
            "detection_id": self.detection_id,
            "bbox": list(self.bbox),
            "score": float(self.score),
            "landmarks": [[float(x), float(y)] for x, y in self.landmarks],
            "crop_path": self.crop_path,
        }


class YuNetFaceDetector:
    def __init__(
        self,
        model_path: str | Path,
        score_threshold: float = 0.75,
        nms_threshold: float = 0.30,
        top_k: int = 5000,
    ) -> None:
        self.model_path = Path(model_path)
        self.score_threshold = float(score_threshold)
        self.nms_threshold = float(nms_threshold)
        self.top_k = int(top_k)
        self.detector = None
        self._last_input_size: tuple[int, int] | None = None

    def ensure_model(self) -> Path:
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        if self.model_path.exists() and self.model_path.stat().st_size > 1024:
            return self.model_path

        last_error: Exception | None = None
        for url in YUNET_URLS:
            try:
                urllib.request.urlretrieve(url, str(self.model_path))
                if self.model_path.exists() and self.model_path.stat().st_size > 1024:
                    return self.model_path
            except Exception as exc:  # pragma: no cover - best effort download
                last_error = exc

        raise RuntimeError(
            "Could not download YuNet model automatically. "
            f"Please place 'face_detection_yunet_2023mar.onnx' at: {self.model_path}"
        ) from last_error

    def _ensure_detector(self, width: int, height: int) -> None:
        self.ensure_model()

        if self.detector is None:
            self.detector = cv2.FaceDetectorYN.create(
                str(self.model_path),
                "",
                (width, height),
                self.score_threshold,
                self.nms_threshold,
                self.top_k,
            )
            self._last_input_size = (width, height)
            return

        if self._last_input_size != (width, height):
            self.detector.setInputSize((width, height))
            self._last_input_size = (width, height)

    def detect(self, frame) -> list[dict]:
        height, width = frame.shape[:2]
        self._ensure_detector(width, height)

        assert self.detector is not None
        retval, faces = self.detector.detect(frame)
        if retval is None or faces is None:
            return []

        detections: list[dict] = []
        for row in faces:
            x, y, w, h = row[:4]
            landmarks_flat = row[4:14]
            score = float(row[14])

            bbox = (
                max(0, int(round(x))),
                max(0, int(round(y))),
                max(1, int(round(w))),
                max(1, int(round(h))),
            )

            landmarks: list[tuple[float, float]] = []
            for idx in range(0, len(landmarks_flat), 2):
                landmarks.append((float(landmarks_flat[idx]), float(landmarks_flat[idx + 1])))

            detections.append(
                {
                    "bbox": bbox,
                    "score": score,
                    "landmarks": landmarks,
                }
            )

        return detections


def crop_face(frame, bbox: tuple[int, int, int, int], padding_ratio: float = 0.20):
    frame_h, frame_w = frame.shape[:2]
    x, y, w, h = bbox

    pad_x = int(round(w * padding_ratio))
    pad_y = int(round(h * padding_ratio))

    x0 = max(0, x - pad_x)
    y0 = max(0, y - pad_y)
    x1 = min(frame_w, x + w + pad_x)
    y1 = min(frame_h, y + h + pad_y)

    return frame[y0:y1, x0:x1].copy()


def process_video_faces(
    video_path: str | Path,
    output_json_path: str | Path,
    crops_dir: str | Path,
    model_path: str | Path,
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict:
    video_path = Path(video_path)
    output_json_path = Path(output_json_path)
    crops_dir = Path(crops_dir)
    model_path = Path(model_path)

    crops_dir.mkdir(parents=True, exist_ok=True)
    output_json_path.parent.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

    detector = YuNetFaceDetector(model_path=model_path)
    detector.ensure_model()

    frames: list[dict] = []
    frame_index = 0
    detection_id = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        raw_detections = detector.detect(frame)
        faces_for_frame: list[dict] = []

        for local_index, raw in enumerate(raw_detections):
            crop = crop_face(frame, raw["bbox"])
            crop_filename = f"frame_{frame_index:06d}_face_{local_index:02d}.jpg"
            crop_path = crops_dir / crop_filename
            if crop.size > 0:
                cv2.imwrite(str(crop_path), crop)

            detection = FaceDetection(
                detection_id=detection_id,
                bbox=raw["bbox"],
                score=raw["score"],
                landmarks=raw["landmarks"],
                crop_path=str(crop_path),
            )
            faces_for_frame.append(detection.to_dict())
            detection_id += 1

        frames.append(
            {
                "frame_index": frame_index,
                "time_seconds": frame_index / float(fps),
                "faces": faces_for_frame,
            }
        )

        frame_index += 1
        if progress_callback is not None:
            progress_callback(frame_index, frame_count)

    cap.release()

    result = {
        "video_path": str(video_path),
        "fps": float(fps),
        "width": width,
        "height": height,
        "frame_count": frame_count,
        "detector": "YuNet",
        "model_path": str(model_path),
        "frames": frames,
    }

    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result
