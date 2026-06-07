# immersive-captions2

Bu sürüm temizlenmiş ve tek amaca odaklanmış sürümdür:

- video oynatma
- yüz JSON yükleme
- identity JSON yükleme
- transcript JSON yükleme
- transcript satırlarını yüzlerin biraz altında gösterme
- SFX satırlarını sabit x,y konumunda gösterme

## Ana dosyalar

- `main.py`
  - uygulama giriş noktası
- `player_window.py`
  - side panel arayüzü
  - video, yüz JSON, identity JSON ve transcript JSON yükleme
  - son açılan dosyaları otomatik geri yükleme
- `detection_store.py`
  - yüz, identity ve transcript verilerini okur
- `detection_renderer.py`
  - kutuları, isim etiketlerini ve transcript caption'larını çizer

## Yardımcı araçlar

- `face_tracker.py`
  - videodan frame-by-frame yüz çıkarır ve crop üretir
- `extract_faces.py`
  - CLI extraction aracı
- `cluster_faces.py`
  - crop'lardan identity cluster üretir
- `review_identities.py`
  - preview sheet / html üretir
- `review_identities_app.py`
  - identity düzenleme aracı
- `standardize_face_jsons.py`
  - eski JSON dosyalarını absolute path standardına çevirir

## Temizlenen / kaldırılan dosyalar

Bu sürümden çıkarıldı:
- `caption_model.py`
- `caption_renderer.py`
- `brief.md`

Çünkü bunlar eski group-based caption sistemine aitti ve yeni transcript + face identity renderer ile çakışıyordu.

## Kullanım

1. Video aç
2. Face JSON aç
3. Identities JSON aç
4. Transcript JSON aç
5. Play

Beklenen davranış:
- `type = "dialogue"` olan satırlar, transcript içindeki `name` ile identity JSON içindeki `manual_name` eşleşirse ilgili yüzün biraz altında görünür
- `type = "sfx"` olan satırlar, `x` ve `y` koordinatlarında görünür
- uygulama son açılan dosyaları otomatik geri yüklemeye çalışır


## Transcript timing

- Transcript entries can now include optional `end_time`.
- If `end_time` is missing, the app computes a readable default duration automatically.
- Active captions are now independent per entry, so one character speaking will not immediately replace another character\'s caption just because the next global timestamp started.


## Caption font size

Caption size is controlled in:

- `detection_renderer.py`
- setting: `self.caption_font_point_size = 16`

You can make subtitles bigger or smaller by changing that number.

## Export

The player now has an **Export Captioned MP4** button.

How it works:
- exports the video with the current transcript captions burned in
- uses the current face / identity / transcript data
- keeps the current overlay visibility settings
- tries to keep the original audio by muxing it back with `ffmpeg`
- if audio muxing is not available, it still exports a silent MP4
