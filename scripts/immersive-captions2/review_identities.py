from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np


THUMB_SIZE = (140, 140)
TILE_MARGIN = 10
HEADER_HEIGHT = 56
TEXT_COLOR = (255, 255, 255)
BG_COLOR = (34, 34, 34)
CARD_BG = (58, 58, 58)


def load_identities(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_and_fit_image(image_path: Path, thumb_size: tuple[int, int]) -> np.ndarray:
    img = cv2.imread(str(image_path))
    if img is None or img.size == 0:
        return np.full((thumb_size[1], thumb_size[0], 3), 30, dtype=np.uint8)

    target_w, target_h = thumb_size
    h, w = img.shape[:2]
    scale = min(target_w / max(1, w), target_h / max(1, h))
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

    canvas = np.full((target_h, target_w, 3), 25, dtype=np.uint8)
    x = (target_w - new_w) // 2
    y = (target_h - new_h) // 2
    canvas[y:y + new_h, x:x + new_w] = resized
    return canvas


def make_contact_sheet(identity: dict[str, Any], output_path: Path, columns: int = 4) -> None:
    sample_crops = [Path(p) for p in identity.get("sample_crops", [])]
    if not sample_crops:
        return

    rows = (len(sample_crops) + columns - 1) // columns
    thumb_w, thumb_h = THUMB_SIZE
    sheet_w = columns * thumb_w + (columns + 1) * TILE_MARGIN
    sheet_h = HEADER_HEIGHT + rows * thumb_h + (rows + 1) * TILE_MARGIN

    sheet = np.full((sheet_h, sheet_w, 3), BG_COLOR, dtype=np.uint8)

    title = f"identity_{identity.get('identity_id', -1)}  detections={identity.get('num_detections', 0)}"
    cv2.putText(sheet, title, (TILE_MARGIN, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.72, TEXT_COLOR, 2, cv2.LINE_AA)
    cv2.putText(sheet, "manual_name: ________   status: candidate / ignore", (TILE_MARGIN, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (210, 210, 210), 1, cv2.LINE_AA)

    for index, crop_path in enumerate(sample_crops):
        row = index // columns
        col = index % columns
        x0 = TILE_MARGIN + col * (thumb_w + TILE_MARGIN)
        y0 = HEADER_HEIGHT + TILE_MARGIN + row * (thumb_h + TILE_MARGIN)

        cv2.rectangle(sheet, (x0 - 1, y0 - 1), (x0 + thumb_w + 1, y0 + thumb_h + 1), CARD_BG, 2)
        thumb = read_and_fit_image(crop_path, THUMB_SIZE)
        sheet[y0:y0 + thumb_h, x0:x0 + thumb_w] = thumb

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), sheet)


def build_html(identity_data: dict[str, Any], preview_dir: Path, output_html: Path) -> None:
    identities = identity_data.get("identities", [])
    items: list[str] = []

    for identity in identities:
        identity_id = identity.get("identity_id", -1)
        preview_name = f"identity_{identity_id:03d}.png"
        preview_path = preview_dir / preview_name
        label = identity.get("manual_name") or ""
        status = identity.get("status", "candidate")
        num_detections = identity.get("num_detections", 0)
        time_range = identity.get("time_range", [0, 0])
        items.append(
            f"""
            <div class=\"card\">
              <img src=\"{html.escape(preview_name)}\" alt=\"identity {identity_id}\" />
              <div class=\"meta\">
                <div><strong>identity_{identity_id}</strong></div>
                <div>detections: {num_detections}</div>
                <div>time: {time_range[0]:.2f}s - {time_range[1]:.2f}s</div>
                <div>manual_name: <code>{html.escape(str(label))}</code></div>
                <div>status: <code>{html.escape(str(status))}</code></div>
              </div>
            </div>
            """
        )

    html_text = f"""
<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <title>Identity Review</title>
  <style>
    body {{ font-family: Arial, sans-serif; background: #121212; color: #f0f0f0; margin: 24px; }}
    h1 {{ margin-bottom: 10px; }}
    p {{ color: #cccccc; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 18px; }}
    .card {{ background: #1d1d1d; border: 1px solid #333; border-radius: 10px; overflow: hidden; }}
    .card img {{ width: 100%; display: block; background: #000; }}
    .meta {{ padding: 12px 14px; line-height: 1.55; }}
    code {{ background: #2a2a2a; padding: 2px 5px; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>Identity Review</h1>
  <p>Edit the generated <code>face_identities.json</code> file manually and set <code>manual_name</code> or <code>status=ignore</code> for identities you do not want to use.</p>
  <div class=\"grid\">{''.join(items)}</div>
</body>
</html>
"""
    output_html.write_text(html_text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate contact sheets and an HTML review page for clustered identities.")
    parser.add_argument("face_identities_json", type=Path, help="Path to face_identities.json")
    parser.add_argument("--preview-dir", type=Path, default=None, help="Directory to save preview images")
    args = parser.parse_args()

    face_identities_json = args.face_identities_json.resolve()
    base_dir = face_identities_json.with_suffix("")
    preview_dir = args.preview_dir or (base_dir.parent / f"{base_dir.name}.previews")

    data = load_identities(face_identities_json)
    identities = data.get("identities", [])

    preview_dir.mkdir(parents=True, exist_ok=True)
    for identity in identities:
        identity_id = int(identity.get("identity_id", -1))
        output_path = preview_dir / f"identity_{identity_id:03d}.png"
        make_contact_sheet(identity, output_path)

    html_path = preview_dir / "index.html"
    build_html(data, preview_dir, html_path)

    print(f"Saved previews to: {preview_dir}")
    print(f"Open this file in a browser: {html_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
