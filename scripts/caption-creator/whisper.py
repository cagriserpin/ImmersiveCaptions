import json
from pathlib import Path

from faster_whisper import WhisperModel

# whisper.py -> scripts/caption-creator/whisper.py
# project root -> iki klasör yukarı
PROJECT_ROOT = Path(__file__).resolve().parents[2]

AUDIO_PATH = PROJECT_ROOT / "media" / "audio" / "yan_yana.mp3"
OUTPUT_PATH = PROJECT_ROOT / "media" / "captions" / "yan_yana" / "words.json"

print("Loading model...")
model = WhisperModel("small", device="cpu", compute_type="int8")
print("Model loaded.")

# Output klasörü yoksa oluştur
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

segments, info = model.transcribe(
    str(AUDIO_PATH),
    language="tr",
    beam_size=5,
    best_of=5,
    word_timestamps=True,
    vad_filter=True,
    condition_on_previous_text=True,
)

words_data = []

for segment in segments:
    if segment.words:
        for word in segment.words:
            if word.start is not None and word.end is not None:
                text = word.word.strip()
                if text:
                    words_data.append({
                        "text": text,
                        "start": round(float(word.start), 3),
                        "end": round(float(word.end), 3)
                    })

with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(words_data, f, ensure_ascii=False, indent=2)

print(f"Saved {len(words_data)} words to {OUTPUT_PATH}")