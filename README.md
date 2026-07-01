# Steam Splitter PRO

Steam Workshop / vitrin görselleri için görsel **bölme** + **Steam Community upload otomasyonu**
masaüstü aracı. customtkinter ile yazılmış koyu temalı bir GUI.

## Ne işe yarar?

- Bir görseli (PNG/JPG/WEBP/**GIF**) seçilen şablona göre dikey parçalara böler
  (Workshop 5-parça, çizim vitrini 2-parça, ekran görüntüsü tek parça, veya özel şablonlar).
- Animasyonlu GIF'leri kare kare bölerek yine animasyonlu parçalar üretir (gifsicle ile optimize).
- İsteğe bağlı **Border FX** (kenarlık şablonu + renk + glow) uygular.
- Parçaları Playwright ile bir tarayıcı oturumu üzerinden Steam Community'ye yüklemeyi otomatikleştirir.
- Ayrı bir **GIF / WebP Maker** (`GİF/gif.py`) ile video → GIF/WebP dönüştürür (ffmpeg).

## Dosya yapısı

| Yol | Açıklama |
|-----|----------|
| `editor.py` | GUI (App + widget'lar + manuel crop). Çalıştırılacak dosya budur. |
| `core.py` | UI'sız saf işleme katmanı (patch/gifsicle/resize/border-fx/GIF-split/process_image). |
| `config.py` | Şablon sabitleri, config/preset yükle-kaydet, Steam manifest yardımcıları. |
| `steam_community_uploader.py` | Playwright tabanlı Steam Community upload alt-süreci. |
| `GİF/gif.py` | Bağımsız GIF/WebP yapım aracı (editörden "GIF Maker" ile açılır). |
| `Border Templates/` | Border FX için kullanılan PNG kenarlık şablonları. |
| `GİF/bin/` | Bundle edilen `ffmpeg`, `ffprobe`, `gifsicle` binary'leri (repoya dahil değil). |
| `steam_splitter_config.json` | Uygulama ayarları (otomatik kaydedilir). |
| `steam_splitter_presets.json` | Özel şablonlar. |
| `steam_notes.txt` | Steam console kodları / linkler (uygulama içinden düzenlenebilir). |
| `tests/` | `core.py`/`config.py`/`GİF/gif.py` için pytest testleri. |

## Kurulum

Python 3.10+ gerekir (tip ipuçları için `str | None` kullanılıyor).

```bash
pip install -r requirements.txt
# Playwright tarayıcılarını ilk kez indir (upload otomasyonu için):
python -m playwright install
```

`requirements.txt`: `customtkinter`, `Pillow`, `pynput`, `playwright`, `tkinterdnd2`.

**Bundle binary'ler:** GIF işleme için `ffmpeg`/`ffprobe`/`gifsicle` gerekir. Bunlar `GİF/bin/`
(ve gifsicle için ek olarak proje kökü) altında aranır; PATH'te de bulunabilir. Repoya dahil
edilmezler (boyut nedeniyle `.gitignore`'da) — ayrı indirip ilgili klasöre koy.

## Çalıştırma

```bash
python editor.py
```

Bir resmi pencereye **sürükle-bırak** (ya da "Dosya/Klasör Seç"), bir şablon seç, **Böl**'e bas.
Klasör seçip **Toplu Böl** ile tüm klasörü işleyebilirsin. Çıktılar `output/` altına yazılır.

## Notlar / bilinen davranışlar

- **PNG/GIF son-byte patch**: Workshop vitrin hilesi için çıktının son byte'ı `0x21` yapılır
  (şablonda "patch" açıksa). Bu dosyayı teknik olarak "bozar" ama çoğu görüntüleyici tolere eder.
- **Upload otomasyonu** ayrı bir tarayıcı profili (`.steam_browser_profile/`) kullanır; ilk
  çalıştırmada Steam'e giriş yapman gerekir. Manuel modda gönderim 30 dk içinde tamamlanmazsa
  o parça atlanır; monitör penceresinden **İptal Et** ile süreci durdurabilirsin.
- `auto_submit` açıkken uploader "Kaydet ve Devam Et"e otomatik basar — gözetimsiz toplu yükleme
  için uygundur; tek tek kontrol etmek istiyorsan ayarlardan kapat.

## Test

```bash
pip install -r requirements-dev.txt
pytest
```

`core.py` ve `config.py` testleri her zaman çalışır (ffmpeg/gifsicle gerektirmez).
`GİF/gif.py` testlerindeki gerçek ffmpeg dönüştürme testleri `GİF/bin/` altında binary'ler
yoksa otomatik atlanır (`skip`); saf fonksiyon testleri (renk/efekt/border-template mantığı)
her koşulda çalışır.

## Sorun giderme

- **Sürükle-bırak çalışmıyor** → `tkinterdnd2` kurulu mu? (`pip install tkinterdnd2`)
- **GIF bölünmüyor / optimize olmuyor** → `GİF/bin/gifsicle.exe` var mı?
- **GIF Maker'da dönüşüm hata veriyor** → `ffmpeg`/`ffprobe` bulunamıyor olabilir (PATH veya `GİF/bin/`).
- **Upload başlamıyor** → `python -m playwright install` çalıştırıldı mı?
