from __future__ import annotations

import argparse
from pathlib import Path

from face_tracker import process_video_faces


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
    args = parser.parse_args()

    video_path = args.video.resolve()
    base_dir = video_path.with_suffix("")
    output_json = args.output_json or (base_dir.parent / f"{base_dir.name}.faces_raw.json")
    crops_dir = args.crops_dir or (base_dir.parent / f"{base_dir.name}.face_crops")

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
