import json
from pathlib import Path

# Bu dosya örneğin scripts/caption-creator/ altında olabilir
PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_PATH = PROJECT_ROOT / "media" / "captions" / "yan_yana" / "words.json"
OUTPUT_PATH = PROJECT_ROOT / "media" / "captions" / "yan_yana" / "yan_yana_plain.json"


def load_words(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def split_into_groups(words: list[dict]) -> list[dict]:
    sentence_endings = {".", "?", "!", "…"}
    groups = []
    current_words = []

    for word in words:
        current_words.append({
            "text": word["text"],
            "start": word["start"],
            "end": word["end"]
        })

        text = word["text"].strip()
        if text and text[-1] in sentence_endings:
            groups.append({
                "sections": [
                    {
                        "type": "dialogue",
                        "speaker": "speaker_a",
                        "words": current_words
                    }
                ]
            })
            current_words = []

    if current_words:
        groups.append({
            "sections": [
                {
                    "type": "dialogue",
                    "speaker": "speaker_a",
                    "words": current_words
                }
            ]
        })

    return groups


def build_caption_json(words: list[dict]) -> dict:
    groups = split_into_groups(words)

    return {
        "defaults": {
            "font": "Calibri",
            "font_size": 25,
            "font_weight": 400,
            "font_color": "#ffffff",
            "font_style": "normal",
            "dim_opacity": 0.35,

            "group_show_time_margin": 0.0,
            "group_disappear_time_margin": 0.0,
            "default_animation_time_margin": 0.0,

            "group_gap": 8,
            "section_gap": 0,
            "section_to_bg_padding_x": 18,
            "section_to_bg_padding_y": 10,
            "section_video_bottom_margin": 80,
            "word_gap": 10,
            "reveal_feather_px": 0
        },
        "speakers": {
            "speaker_a": {
                "font_color": "#ffffff"
            }
        },
        "groups": groups
    }


def main():
    if not INPUT_PATH.exists():
        print(f"Input file not found: {INPUT_PATH}")
        return

    words = load_words(INPUT_PATH)
    caption_data = build_caption_json(words)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(caption_data, f, ensure_ascii=False, indent=2)

    print(f"Saved plain immersive caption to:\n{OUTPUT_PATH}")
    print(f"Total groups: {len(caption_data['groups'])}")


if __name__ == "__main__":
    main()