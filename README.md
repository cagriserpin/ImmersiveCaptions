# Immersive Captions

Immersive Captions, klasik altyazıların sınırlarını aşmayı hedefleyen etkileşimli bir altyazı üretim ve oynatma sistemidir.

Bugünkü standart altyazılar onlarca yıldır aynı temel mantıkla çalışıyor: ekranda konuşulanlar metin olarak gösteriliyor. Bu yaklaşım erişilebilirlik açısından çok değerli olsa da, konuşanın kim olduğu, kelimelerin tam olarak ne zaman söylendiği ve cümlenin hangi duygu ya da tonla aktarıldığı çoğu zaman yeterince iyi yansıtılamıyor. “Caption with Intention” yaklaşımı da tam olarak bu üç temel soruna dikkat çekiyor: **konuşan kişinin net biçimde ayırt edilememesi**, **altyazının konuşmayla yeterince hassas senkronize olmaması** ve **intonasyonun kaybolması**. :contentReference[oaicite:1]{index=1}

Immersive Captions bu fikirden ilham alır ve altyazıyı yalnızca bir metin katmanı olmaktan çıkarıp, sahnenin ritmine ve niyetine eşlik eden görsel bir anlatım aracına dönüştürmeyi amaçlar.

## Neden böyle bir projeye ihtiyaç var?

Bu tarz bir altyazı sistemi üretmek teoride çok güçlü, pratikte ise pahalı ve zaman alıcıdır. Çünkü insan eli değmesi gerekir.

Konuşmacı renklerinin seçilmesi, kelime zamanlarının düzenlenmesi, vurgu anlarının belirlenmesi, animasyonların doğru yerde ve doğru yoğunlukta uygulanması, ses efektleri ile müzik öğelerinin ayrı ele alınması gibi pek çok karar manuel olarak verilir. Mevcut profesyonel iş akışlarında bu süreç; dikkat, zaman, tekrar ve çoğu zaman birden fazla kişinin emeğini gerektirir.

Bizim hedefimiz bu emeği tamamen yok saymak değil; onu **daha yönetilebilir, daha hızlı ve daha erişilebilir** hale getirmektir.

## Projenin amacı

Immersive Captions’ın ana amacı, etkileşimli ve niyet taşıyan altyazılar üretmeyi kolaylaştıran bir altyapı ve araç seti sunmaktır.

Bu proje ile:

- altyazılar konuşan kişiye göre görsel olarak ayrıştırılabilir,
- kelime bazlı zamanlama ile konuşma ritmi takip edilebilir,
- vurgu, şaşkınlık, bağırma, tekrar ve kalabalık tepkileri gibi anlar animasyonla desteklenebilir,
- ses efektleri ve müzik öğeleri klasik altyazıdan daha bilinçli biçimde işlenebilir,
- aynı içerik için hem sade hem de gelişmiş/animasyonlu altyazı versiyonları üretilebilir.

Kısacası hedef, altyazıyı yalnızca “ne söylendi” sorusuna cevap veren bir katman olmaktan çıkarıp, mümkün olduğunca “nasıl söylendi” bilgisini de taşıyan bir yapıya dönüştürmektir.

## Biz ne geliştiriyoruz?

Bu repoda iki temel hedef bir araya geliyor:

### 1. Caption playback/rendering sistemi
Özel bir JSON tabanlı altyazı modeli ile:
- grup bazlı altyazılar,
- konuşmacı bazlı renkler,
- kelime bazlı zamanlama,
- animasyonlar,
- vurgu geçişleri,
- SFX ve müzik öğeleri

oynatılabilir ve sahne üzerinde gerçek zamanlı render edilebilir.

### 2. Caption creator aracı
Asıl büyük hedefimiz, bu sistemi kullanmayı uzmanlara özel ve yavaş bir iş akışı olmaktan çıkarmaktır.

Planladığımız caption creator sayesinde:
- sağ tarafta canlı render önizleme,
- solda altyazı yapısı ve düzenleme alanı,
- altta video edit programlarına benzer zaman çizelgesi,
- seçilebilir ve düzenlenebilir kelime/section/group yapısı,
- yapay zeka destekli öneriler ve hızlandırılmış düzenleme akışı

tek bir araç içinde bir araya gelecek.

Böylece bugün normalde bir ekip ve günler sürebilecek etkileşimli altyazı üretim süreci, gelecekte **tek bir kişi tarafından çok daha kısa sürede** tamamlanabilecek.

## Neden önemli?

Erişilebilirlik sadece metni göstermek değildir. Doğru erişilebilirlik, anlatının niyetini de mümkün olduğunca koruyabilmektir.

Bir karakterin ekrandan değil dış sesten konuşması, bir kelimenin alaycı mı yoksa öfkeli mi söylendiği, bir kalabalığın yükselen tepkisi, bir kahkahanın patlaması ya da bir cümlenin vurgusu; bunların hepsi hikâye anlatımının parçasıdır.

Immersive Captions, bu anlatı katmanlarını daha görünür hale getirmeye çalışan bir araçtır.

## Vizyon

Uzun vadeli vizyonumuz, etkileşimli altyazı üretimini:
- daha hızlı,
- daha sistematik,
- daha erişilebilir,
- daha ucuz
hale getirmektir.

Bugün bu kalite seviyesinde altyazı üretmek yoğun manuel emek gerektiriyor. Biz ise bunu yazılım, iyi bir veri modeli ve yapay zeka destekli düzenleme araçlarıyla dönüştürmek istiyoruz.

Hedefimiz, bu sistemi yalnızca teknik olarak mümkün kılmak değil; aynı zamanda yaratıcılar, editörler ve bağımsız üreticiler için **gerçekten kullanılabilir** hale getirmektir.

## Kısaca

Immersive Captions:

- klasik altyazının eksik bıraktığı anlatı katmanlarını görünür kılmayı amaçlar,
- etkileşimli altyazı üretimini sistematik hale getirir,
- insan emeğini tamamen kaldırmadan, onu çok daha verimli hale getirmeyi hedefler,
- gelecekte yapay zeka destekli bir caption creator ile bu iş akışını tek kişilik bir üretim modeline yaklaştırır.

Bu proje, sadece altyazı göstermek için değil, **altyazıya niyet kazandırmak** için var.