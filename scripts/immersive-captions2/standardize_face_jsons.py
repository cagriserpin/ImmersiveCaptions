
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalize_raw_json(raw_json_path: Path) -> dict:
    raw_json_path = raw_json_path.resolve()
    data = load_json(raw_json_path)

    crops_dir = raw_json_path.with_suffix("").resolve()

    data["json_path"] = str(raw_json_path)
    data["crops_dir"] = str(crops_dir)

    if data.get("video_path"):
        video_path = Path(str(data["video_path"]))
        if not video_path.is_absolute():
            data["video_path"] = str(video_path.resolve())

    if data.get("model_path"):
        model_path = Path(str(data["model_path"]))
        if not model_path.is_absolute():
            data["model_path"] = str(model_path.resolve())

    frames = data.get("frames", [])
    for frame in frames:
        frame_index = int(frame.get("frame_index", 0))
        faces = frame.get("faces", [])
        if not isinstance(faces, list):
            continue
        for face_idx, face in enumerate(faces):
            current = str(face.get("crop_path", "")).strip()
            filename = Path(current).name if current else f"frame_{frame_index:06d}_face_{face_idx:02d}.jpg"
            face["crop_path"] = str((crops_dir / filename).resolve())

    save_json(raw_json_path, data)
    return data


def normalize_identities_json(raw_json_path: Path, identities_json_path: Path) -> dict:
    raw_json_path = raw_json_path.resolve()
    identities_json_path = identities_json_path.resolve()

    raw = load_json(raw_json_path)
    data = load_json(identities_json_path)

    crops_dir = Path(str(raw.get("crops_dir", raw_json_path.with_suffix("")))).resolve()
    data["identity_json_path"] = str(identities_json_path)
    data["source_faces_raw_json"] = str(raw_json_path)
    data["source_crops_dir"] = str(crops_dir)
    data.setdefault("label_options", [])

    det_to_crop: dict[int, Path] = {}
    for frame in raw.get("frames", []):
        for face_idx, face in enumerate(frame.get("faces", [])):
            det_id = face.get("detection_id")
            if det_id is None:
                continue
            crop = Path(str(face.get("crop_path", "")))
            if not crop.name:
                crop = crops_dir / f"frame_{int(frame.get('frame_index', 0)):06d}_face_{face_idx:02d}.jpg"
            elif not crop.is_absolute():
                crop = crops_dir / crop.name
            det_to_crop[int(det_id)] = crop.resolve()

    for identity in data.get("identities", []):
        detection_ids = [int(x) for x in identity.get("detection_ids", [])]
        identity.setdefault("detection_overrides", {})

        if detection_ids:
            rep = det_to_crop.get(detection_ids[0])
            if rep is not None:
                identity["representative_crop"] = str(rep)
            sample_crops = []
            for det_id in detection_ids[:12]:
                crop = det_to_crop.get(det_id)
                if crop is not None:
                    sample_crops.append(str(crop))
            identity["sample_crops"] = sample_crops

    save_json(identities_json_path, data)
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize existing face tracking JSON files to the absolute-path standard.")
    parser.add_argument("raw_json", type=Path, help="Path to *.face_tracks.json")
    parser.add_argument("--identities-json", type=Path, default=None, help="Optional path to *.face_identities.json")
    args = parser.parse_args()

    raw_json_path = args.raw_json.resolve()
    normalize_raw_json(raw_json_path)
    print(f"Normalized raw JSON: {raw_json_path}")

    if args.identities_json is not None:
        identities_path = args.identities_json.resolve()
        normalize_identities_json(raw_json_path, identities_path)
        print(f"Normalized identities JSON: {identities_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
