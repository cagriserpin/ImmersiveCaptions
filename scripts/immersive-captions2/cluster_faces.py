
from __future__ import annotations

import argparse
import json
import math
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from sklearn.cluster import DBSCAN


SFACE_URLS = [
    "https://huggingface.co/opencv/face_recognition_sface/resolve/main/face_recognition_sface_2021dec.onnx",
    "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
]

CROP_PADDING_RATIO = 0.20


@dataclass
class FaceCandidate:
    detection_id: int
    frame_index: int
    time_seconds: float
    bbox: tuple[int, int, int, int]
    score: float
    landmarks: list[tuple[float, float]]
    crop_path: Path
    embedding: np.ndarray

    @property
    def area(self) -> int:
        return int(self.bbox[2] * self.bbox[3])

    @property
    def quality(self) -> float:
        return float(self.score) * math.sqrt(max(1.0, self.area))


class SFaceEmbedder:
    def __init__(self, model_path: str | Path) -> None:
        self.model_path = Path(model_path)
        self.recognizer = None

    def ensure_model(self) -> Path:
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        if self.model_path.exists() and self.model_path.stat().st_size > 1024:
            return self.model_path

        last_error: Exception | None = None
        for url in SFACE_URLS:
            try:
                urllib.request.urlretrieve(url, str(self.model_path))
                if self.model_path.exists() and self.model_path.stat().st_size > 1024:
                    return self.model_path
            except Exception as exc:
                last_error = exc

        raise RuntimeError(
            "Could not download SFace model automatically. "
            f"Please place 'face_recognition_sface_2021dec.onnx' at: {self.model_path}"
        ) from last_error

    def _ensure_recognizer(self):
        if self.recognizer is None:
            self.ensure_model()
            self.recognizer = cv2.FaceRecognizerSF.create(str(self.model_path), "")
        return self.recognizer

    def cheap_fallback_embedding(self, crop_img: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (48, 48), interpolation=cv2.INTER_LINEAR)
        gray = cv2.equalizeHist(gray)
        feature = gray.astype(np.float32).reshape(-1)
        norm = float(np.linalg.norm(feature))
        if norm > 1e-8:
            feature = feature / norm
        return feature

    def embed(self, crop_img: np.ndarray, face_row: np.ndarray | None = None) -> np.ndarray:
        recognizer = self._ensure_recognizer()

        aligned = None
        if face_row is not None:
            try:
                aligned = recognizer.alignCrop(crop_img, face_row)
            except Exception:
                aligned = None

        if aligned is None or getattr(aligned, "size", 0) == 0:
            aligned = cv2.resize(crop_img, (112, 112), interpolation=cv2.INTER_LINEAR)

        try:
            feature = recognizer.feature(aligned)
            if feature is None:
                raise RuntimeError("SFace returned None.")
            feature = np.asarray(feature, dtype=np.float32).reshape(-1)
            norm = float(np.linalg.norm(feature))
            if norm > 1e-8:
                feature = feature / norm
            return feature
        except Exception:
            return self.cheap_fallback_embedding(crop_img)


def load_faces_raw(json_path: Path) -> dict[str, Any]:
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_local_face_row(
    detection: dict[str, Any],
    frame_width: int,
    frame_height: int,
    padding_ratio: float = CROP_PADDING_RATIO,
) -> np.ndarray | None:
    bbox = detection.get("bbox", [])
    landmarks = detection.get("landmarks", [])
    score = float(detection.get("score", 0.0))
    if len(bbox) != 4 or len(landmarks) != 5:
        return None

    x, y, w, h = [int(v) for v in bbox]
    pad_x = int(round(w * padding_ratio))
    pad_y = int(round(h * padding_ratio))

    x0 = max(0, x - pad_x)
    y0 = max(0, y - pad_y)
    x1 = min(frame_width, x + w + pad_x)
    y1 = min(frame_height, y + h + pad_y)
    if x1 <= x0 or y1 <= y0:
        return None

    local_bbox_x = float(x - x0)
    local_bbox_y = float(y - y0)
    row = [local_bbox_x, local_bbox_y, float(w), float(h)]

    for point in landmarks:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            return None
        row.append(float(point[0]) - float(x0))
        row.append(float(point[1]) - float(y0))

    row.append(score)
    return np.asarray([row], dtype=np.float32)


def resolve_crop_path(face: dict[str, Any], faces_raw_json: Path, crops_dir: Path | None = None) -> Path:
    crop_path = Path(str(face.get("crop_path", "")))
    if crop_path.exists():
        return crop_path.resolve()

    if crops_dir is not None:
        alt0 = (crops_dir / crop_path.name).resolve()
        if alt0.exists():
            return alt0

    alt1 = (faces_raw_json.parent / crop_path.name).resolve()
    if alt1.exists():
        return alt1

    alt2 = (faces_raw_json.with_suffix("") / crop_path.name).resolve()
    if alt2.exists():
        return alt2

    return crop_path


def iter_face_candidates(
    raw_data: dict[str, Any],
    faces_raw_json: Path,
    min_score: float,
    min_face_size: int,
    embedder: SFaceEmbedder,
) -> list[FaceCandidate]:
    frame_width = int(raw_data.get("width") or 0)
    frame_height = int(raw_data.get("height") or 0)
    crops_dir_value = str(raw_data.get("crops_dir", "")).strip()
    crops_dir = Path(crops_dir_value) if crops_dir_value else None

    candidates: list[FaceCandidate] = []
    frames = raw_data.get("frames", [])
    total = len(frames)

    skipped_low_score = 0
    skipped_small = 0
    missing_crop = 0
    unreadable_crop = 0

    for frame_no, frame in enumerate(frames):
        if frame_no % 100 == 0 and total:
            print(f"Embedding faces: {frame_no}/{total} frames...", flush=True)

        frame_index = int(frame.get("frame_index") or frame_no)
        time_seconds = float(frame.get("time_seconds") or 0.0)

        for face_idx, face in enumerate(frame.get("faces", [])):
            bbox = face.get("bbox", [])
            if len(bbox) != 4:
                continue

            x, y, w, h = [int(v) for v in bbox]
            score = float(face.get("score") or 0.0)
            if score < min_score:
                skipped_low_score += 1
                continue
            if min(w, h) < min_face_size:
                skipped_small += 1
                continue

            crop_path = resolve_crop_path(face, faces_raw_json, crops_dir=crops_dir)
            if not crop_path.exists():
                # filename fallback from frame/local indices
                guessed = None
                if crops_dir is not None:
                    guessed = (crops_dir / f"frame_{frame_index:06d}_face_{face_idx:02d}.jpg").resolve()
                    if guessed.exists():
                        crop_path = guessed

            if not crop_path.exists():
                missing_crop += 1
                continue

            crop_img = cv2.imread(str(crop_path))
            if crop_img is None or crop_img.size == 0:
                unreadable_crop += 1
                continue

            face_row = build_local_face_row(face, frame_width, frame_height)
            embedding = embedder.embed(crop_img, face_row)

            landmarks = [
                tuple(float(v) for v in point)
                for point in face.get("landmarks", [])
                if isinstance(point, (list, tuple)) and len(point) == 2
            ]
            candidates.append(
                FaceCandidate(
                    detection_id=int(face.get("detection_id", -1)),
                    frame_index=frame_index,
                    time_seconds=time_seconds,
                    bbox=(x, y, w, h),
                    score=score,
                    landmarks=landmarks,
                    crop_path=crop_path.resolve(),
                    embedding=embedding,
                )
            )

    print(f"Skipped low score: {skipped_low_score}")
    print(f"Skipped small face: {skipped_small}")
    print(f"Missing crop file: {missing_crop}")
    print(f"Unreadable crop file: {unreadable_crop}")
    return candidates


def cluster_candidates(candidates: list[FaceCandidate], eps: float, min_samples: int) -> np.ndarray:
    if not candidates:
        return np.empty((0,), dtype=np.int32)

    embeddings = np.stack([candidate.embedding for candidate in candidates], axis=0)
    clustering = DBSCAN(eps=eps, min_samples=min_samples, metric="cosine")
    labels = clustering.fit_predict(embeddings)
    return labels.astype(np.int32)


def build_identities(
    candidates: list[FaceCandidate],
    labels: np.ndarray,
    preview_limit: int,
) -> list[dict[str, Any]]:
    grouped: dict[int, list[FaceCandidate]] = {}
    for candidate, label in zip(candidates, labels.tolist()):
        if label < 0:
            continue
        grouped.setdefault(int(label), []).append(candidate)

    identities: list[dict[str, Any]] = []
    for identity_id, group in sorted(grouped.items(), key=lambda item: item[0]):
        group.sort(key=lambda c: (-c.quality, c.time_seconds))
        best = group[0]
        sample_crops = [str(candidate.crop_path.resolve()) for candidate in group[:preview_limit]]
        detection_ids = [candidate.detection_id for candidate in group]
        frame_indices = sorted({candidate.frame_index for candidate in group})
        time_values = [candidate.time_seconds for candidate in group]

        identities.append(
            {
                "identity_id": int(identity_id),
                "manual_name": "",
                "status": "candidate",
                "num_detections": len(group),
                "best_score": float(best.score),
                "representative_crop": str(best.crop_path.resolve()),
                "sample_crops": sample_crops,
                "detection_ids": detection_ids,
                "frame_indices": frame_indices,
                "time_range": [float(min(time_values)), float(max(time_values))],
                "detection_overrides": {},
            }
        )

    identities.sort(key=lambda item: (-int(item["num_detections"]), int(item["identity_id"])))
    for new_id, identity in enumerate(identities):
        identity["identity_id"] = new_id
    return identities


def build_detection_to_identity(labels: np.ndarray, identities: list[dict[str, Any]], candidates: list[FaceCandidate]) -> dict[int, int]:
    by_old_cluster: dict[int, int] = {}
    for identity in identities:
        det_ids = set(identity.get("detection_ids", []))
        if not det_ids:
            continue
        for candidate, label in zip(candidates, labels.tolist()):
            if candidate.detection_id in det_ids and label >= 0:
                by_old_cluster[int(label)] = int(identity["identity_id"])
                break

    detection_to_identity: dict[int, int] = {}
    for candidate, label in zip(candidates, labels.tolist()):
        if label < 0:
            continue
        if int(label) in by_old_cluster:
            detection_to_identity[int(candidate.detection_id)] = by_old_cluster[int(label)]
    return detection_to_identity


def save_identities(
    output_json: Path,
    raw_json_path: Path,
    raw_data: dict[str, Any],
    candidates: list[FaceCandidate],
    identities: list[dict[str, Any]],
    detection_to_identity: dict[int, int],
    eps: float,
    min_samples: int,
    min_score: float,
    min_face_size: int,
) -> dict[str, Any]:
    output_json = output_json.resolve()
    raw_json_path = raw_json_path.resolve()
    crops_dir_value = str(raw_data.get("crops_dir", "")).strip()
    crops_dir = str(Path(crops_dir_value).resolve()) if crops_dir_value else str(raw_json_path.with_suffix("").resolve())

    result = {
        "identity_json_path": str(output_json),
        "source_faces_raw_json": str(raw_json_path),
        "source_crops_dir": crops_dir,
        "cluster_method": "dbscan_cosine",
        "cluster_params": {
            "eps": float(eps),
            "min_samples": int(min_samples),
            "min_score": float(min_score),
            "min_face_size": int(min_face_size),
        },
        "label_options": [],
        "num_cluster_candidates": len(candidates),
        "num_identities": len(identities),
        "identities": identities,
        "detection_to_identity": detection_to_identity,
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Cluster extracted face detections into unique identities.")
    parser.add_argument("faces_raw_json", type=Path, help="Path to faces_raw.json")
    parser.add_argument("--output-json", type=Path, default=None, help="Path to save face_identities.json")
    parser.add_argument(
        "--model",
        type=Path,
        default=Path(__file__).resolve().parent / "models" / "face_recognition_sface_2021dec.onnx",
        help="Path to the SFace ONNX model file.",
    )
    parser.add_argument("--min-score", type=float, default=0.82, help="Ignore detections below this confidence")
    parser.add_argument("--min-face-size", type=int, default=48, help="Ignore very small faces")
    parser.add_argument("--eps", type=float, default=0.32, help="DBSCAN cosine distance threshold")
    parser.add_argument("--min-samples", type=int, default=4, help="DBSCAN min samples")
    parser.add_argument("--preview-limit", type=int, default=12, help="How many sample crops to keep per identity")
    args = parser.parse_args()

    faces_raw_json = args.faces_raw_json.resolve()
    base_dir = faces_raw_json.with_suffix("")
    output_json = (args.output_json or (base_dir.parent / f"{base_dir.name}.face_identities.json")).resolve()

    raw_data = load_faces_raw(faces_raw_json)
    embedder = SFaceEmbedder(args.model)
    embedder.ensure_model()

    candidates = iter_face_candidates(
        raw_data=raw_data,
        faces_raw_json=faces_raw_json,
        min_score=float(args.min_score),
        min_face_size=int(args.min_face_size),
        embedder=embedder,
    )

    print(f"Valid face candidates: {len(candidates)}", flush=True)
    labels = cluster_candidates(candidates, eps=float(args.eps), min_samples=int(args.min_samples))
    identities = build_identities(candidates, labels, preview_limit=int(args.preview_limit))
    detection_to_identity = build_detection_to_identity(labels, identities, candidates)

    result = save_identities(
        output_json=output_json,
        raw_json_path=faces_raw_json,
        raw_data=raw_data,
        candidates=candidates,
        identities=identities,
        detection_to_identity=detection_to_identity,
        eps=float(args.eps),
        min_samples=int(args.min_samples),
        min_score=float(args.min_score),
        min_face_size=int(args.min_face_size),
    )

    print(f"Saved identities JSON to: {output_json}")
    print(f"Unique identities: {result['num_identities']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
