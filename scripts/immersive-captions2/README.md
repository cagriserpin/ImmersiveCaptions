# immersive-captions2

Bu sürüm artık iki aşamalı ilerliyor:

1. **Phase 1**: videonun her frame'inde yüzleri bulmak ve crop üretmek
2. **Phase 2**: bulunan yüz crop'larını kümelendirip unique identity adayları çıkarmak

Bu aşamada hâlâ altyazı yok. Amaç önce kimlerin tekrar ettiğini bulmak.

## Dosyalar

- `extract_faces.py`
  - videoyu kare kare işler
  - `faces_raw.json` üretir
  - crop klasörü üretir
- `cluster_faces.py`
  - `faces_raw.json` içindeki crop'ları embedding ile karşılaştırır
  - unique identity adayları çıkarır
  - `face_identities.json` üretir
- `review_identities.py`
  - identity kümeleri için contact sheet ve HTML önizleme üretir
  - manuel isim verme ve ignore etme kararını kolaylaştırır
- `player_window.py`
  - Phase 1 önizleme player'ı

## Önerilen akış

### 1) Yüzleri çıkar

```bash
python extract_faces.py /path/to/video.mp4
```

Bu komut şunları üretir:
- `video.faces_raw.json`
- `video.face_crops/`

### 2) Identity adaylarını çıkar

```bash
python cluster_faces.py /path/to/video.faces_raw.json
```

Bu komut şunu üretir:
- `video.faces_raw.face_identities.json`

### 3) Önizlemeleri üret

```bash
python review_identities.py /path/to/video.faces_raw.face_identities.json
```

Bu komut şunları üretir:
- `video.faces_raw.face_identities.previews/identity_000.png`
- `video.faces_raw.face_identities.previews/index.html`

`index.html` dosyasını açıp cluster'ları inceleyebilirsin.

## Phase 2 çıktısı nasıl kullanılacak?

`face_identities.json` içinde her identity için şu alanlar vardır:
- `identity_id`
- `manual_name`
- `status`
- `num_detections`
- `sample_crops`
- `time_range`

Beklenen manuel düzenleme:
- önemli karakterlere `manual_name` ver
- kullanmak istemediklerine `status = ignore` yaz

Örnek:

```json
{
  "identity_id": 0,
  "manual_name": "Mahmut Hoca",
  "status": "named"
}
```

## Notlar

- Phase 2 sadece iyi quality yüzlerden cluster çıkarır.
- Bu yüzden videodaki her detection mutlaka bir identity'ye bağlanmayabilir.
- Bu normaldir; amaç önce güvenilir identity adaylarını çıkarmaktır.
- Toplu konuşmalar ve yüzü görünmeyen sahneler daha sonra manuel olarak girilebilir.

## Absolute path standard

New raw face JSON files now include:

- `json_path`
- `crops_dir`
- absolute `video_path`
- absolute `model_path`
- absolute per-face `crop_path`

New identity JSON files now include:

- `identity_json_path`
- `source_faces_raw_json`
- `source_crops_dir`

If you already have older JSON files, run:

```bash
python standardize_face_jsons.py path/to/hababam.face_tracks.json --identities-json path/to/hababam.face_tracks.face_identities.json
```

This rewrites both JSON files in place so the review tool can locate the crops reliably.
