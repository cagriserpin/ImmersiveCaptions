import json
from faster_whisper import WhisperModel

AUDIO_PATH = "audio/audio.mp3"
OUTPUT_PATH = "words/words.json"

print("Loading model...")
model = WhisperModel("small", device="cpu", compute_type="int8")
print("Model loaded.")

segments, info = model.transcribe(
    AUDIO_PATH,
    language="en",
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