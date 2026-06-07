
from __future__ import annotations

import argparse
import json
from pathlib import Path

from face_tracker import process_video_faces, normalize_existing_paths_in_result


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract faces from every frame of a video.")
    parser.add_argument("video", type=Path, help="Path to the input video.")
    parser.add_argument("--output-json", type=Path, default=None, help="Path to save faces_raw.json")
    parser.add_argument("--crops-dir", type=Path, default=None, help="Directory to save face crops")
    parser.add_argument(
        "--model",
        type=Path,
        default=Path(__file__).resolve().parent / "models" / "face_detection_yunet_2023mar.onnx",
        help="Path to the YuNet ONNX model file.",
    )
    parser.add_argument(
        "--normalize-only",
        action="store_true",
        help="Do not extract again. Only rewrite an existing raw JSON with absolute json_path, crops_dir and crop_path fields.",
    )
    args = parser.parse_args()

    video_path = args.video.resolve()
    base_dir = video_path.with_suffix("")
    output_json = (args.output_json or (base_dir.parent / f"{base_dir.name}.face_tracks.json")).resolve()
    crops_dir = (args.crops_dir or (base_dir.parent / f"{base_dir.name}.face_tracks")).resolve()

    if args.normalize_only:
        with open(output_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        data = normalize_existing_paths_in_result(data, output_json, crops_dir)
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Normalized JSON in place: {output_json}")
        print(f"Crops directory set to: {crops_dir}")
        return 0

    def progress(done: int, total: int) -> None:
        if total > 0 and done % 25 == 0:
            print(f"Processed {done}/{total} frames...", flush=True)

    result = process_video_faces(
        video_path=video_path,
        output_json_path=output_json,
        crops_dir=crops_dir,
        model_path=args.model,
        progress_callback=progress,
    )

    print(f"Saved JSON to: {output_json}")
    print(f"Saved crops to: {crops_dir}")
    print(f"Frames processed: {len(result['frames'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
