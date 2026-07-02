# SplitForge — Steam Showcase Studio

Steam Workshop / vitrin görselleri için görsel **bölme** + **Steam Community upload otomasyonu**
masaüstü aracı. customtkinter ile yazılmış koyu temalı bir GUI.

> İkon `make_icon.py` ile üretilir (`python make_icon.py` → `app_icon.ico` + `app_icon.png`).

## Ne işe yarar?

- Bir görseli (PNG/JPG/WEBP/**GIF**) seçilen şablona göre dikey parçalara böler
  (Workshop 5-parça, çizim vitrini 2-parça, ekran görüntüsü tek parça, veya özel şablonlar).
- **Çoklu bant**: tek yüksek çözünürlüklü fotoğraftan üstten alta N adet 5'li set üretir
  ("Konumu Seç, Gerisini Otomatik Böl" + "Bant sayısı") — vitrine sırayla yüklenince
  kesintisiz tek görsel gibi görünür. Başlangıç konumunu crop penceresinde sen seçersin
  (ya da "Ortala" ile tek tık).
- Animasyonlu GIF'leri kare kare bölerek yine animasyonlu parçalar üretir (gifsicle ile optimize).
- **Efektler** (tek sekmede, bölme sırasında otomatik uygulanır): Border FX (kenarlık şablonu +
  renk + glow), Metin Katmanı (başlık/imza, 7 konum, renk/boyut/opaklık), Otomatik İyileştir
  (kontrast/doygunluk/keskinlik). Efektler parçalara değil TÜM görsele tek seferde uygulanır —
  parçalar yan yana dizilince renk/metin bütünlüğü bozulmaz.
- **Profiller**: şablon + efekt + upload ayarlarını isimli profil olarak kaydet, tek tıkla uygula.
- **Projeler**: üzerinde çalıştığın işin tam durumunu (dosyalar + şablon + çıktı klasörü +
  efektler + upload URL) kaydet; "Aç" ile aynen geri dön.
- **Toplu upload kuyruğu**: birden fazla projeyi işaretle, sırayla bölünüp Steam Community'ye
  yüklensin (proje başına 35 dk emniyet zaman sınırı, İptal ile güvenli durdurma).
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
| `applog.py` | Ortak log altyapısı — her şey `steam_splitter.log`a da yazılır. |
| `steam_splitter_config.json` | Uygulama ayarları (otomatik kaydedilir). |
| `steam_splitter_presets.json` | Özel şablonlar. |
| `steam_splitter_profiles.json` | Kayıtlı profiller (şablon+efekt+upload kombinasyonları). |
| `steam_splitter_projects.json` | Kayıtlı projeler (aktif iş durumları). |
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
- Uploader yalnızca **sözleşme/onay** niteliğindeki checkbox'ları işaretler (agree/terms/kabul...);
  Steam formuna eklenen tanımadığı kutulara dokunmaz, atladıklarını loglar.
- Bir sorun olduğunda önce `steam_splitter.log` dosyasına bak — tüm hata/işlem kayıtları orada
  (uygulama konsolsuz başlatılmış olsa bile).

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
