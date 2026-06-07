# Immersive Captions 2 — Phase 1

This version focuses only on the first phase:

- detect faces on every frame
- save raw face detections
- save cropped face images
- preview those detections on top of the video

Subtitles are intentionally out of scope for this step.

## Files

- `main.py` — app entrypoint
- `player_window.py` — video player + detection preview UI
- `face_tracker.py` — YuNet-based face extraction pipeline
- `extract_faces.py` — CLI entrypoint for batch extraction
- `detection_store.py` — reads `faces_raw.json`
- `detection_renderer.py` — draws boxes / landmarks / labels

## Outputs

When you extract faces for a video, the app writes:

- `your_video.faces_raw.json`
- `your_video.faces_raw/` (face crop images)

## Notes

- This step processes **every frame**
- It uses a stronger detector than the previous prototype
- Manual naming / identity clustering will come in the next phase

## Run

```bash
python main.py
```

## CLI extraction

```bash
python extract_faces.py /path/to/video.mp4
```
