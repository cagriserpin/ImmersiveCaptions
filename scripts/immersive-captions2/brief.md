# Phase 2 Brief

## Amaç

Phase 1'de bulunan ham yüzleri şimdi **unique identity adaylarına** dönüştürmek.

Bu aşamada hedef:
- videoda tekrar eden yüzleri kümelendirmek
- önemli karakterleri ayırmak
- kullanıcıya manuel isim verme ve ignore etme imkânı vermek

## Girdi
- `faces_raw.json`
- `face_crops/`

## Çıktı
- `face_identities.json`
- preview klasörü
- `index.html` review sayfası

## Kullanım mantığı
1. Face extraction yapılır.
2. Cluster çıkarılır.
3. Kullanıcı önemli karakterleri isimlendirir.
4. Gereksiz identity'ler ignore edilir.
5. Sonraki aşamada sadece bu isimlendirilmiş karakterler takip edilir.

## Bu aşamada ne yok?
- altyazı bağlama yok
- crowd konuşma yerleştirme yok
- nihai karakter tracking yok

## Sonraki aşama
- manuel isim verilmiş identity'leri videoda kutu + isim olarak göstermek
- ignore edilenleri göstermemek
