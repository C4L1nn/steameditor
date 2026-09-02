"""core.py — Steam Splitter PRO saf işleme katmanı (UI bağımsız).

editor.py bu modülden import eder. Buradaki fonksiyonlar Tkinter'a bağlı
değildir; doğrudan PIL ile çalışır ve headless test edilebilir.
"""
import os
import subprocess
import platform
import shutil

from PIL import Image, ImageSequence, ImageDraw, ImageFilter, ImageFont, ImageOps, ImageEnhance, ImageChops

try:
    from applog import get_logger  # kök monolit ile birlikte çalışırken
except ImportError:  # paket içi kullanım — döngüsel import olmadan sade logger
    import logging

    def get_logger(name: str = "core") -> logging.Logger:
        return logging.getLogger(f"steameditor.{name}")

_log = get_logger("core")


# Windows'ta alt süreçlerin konsol penceresi yanıp sönmesini engelle
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


# ==========================================================
#   PLATFORM YARDIMCISI — Klasör açma (Windows/Mac/Linux)
# ==========================================================

def open_folder(path: str):
    """Klasörü varsayılan dosya yöneticisinde açar (cross-platform)."""
    try:
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":  # macOS
            subprocess.Popen(["open", path])
        else:                                # Linux ve diğer
            subprocess.Popen(["xdg-open", path])
    except Exception as e:
        _log.error(f"[OPEN FOLDER ERR] {e}")


# ==========================================================
#   PNG LAST BYTE PATCH (Workshop Hilesi)
# ==========================================================

def patch_png_last_byte(path: str, value: int = 0x21):
    """PNG son byte'ını değiştir (Workshop vitrin hack'i)."""
    try:
        with open(path, "rb") as f:
            data = bytearray(f.read())
        if data:
            data[-1] = value
            with open(path, "wb") as f:
                f.write(data)
        _log.info(f"[PATCH] {os.path.basename(path)} -> last byte = 0x{value:02X}")
    except Exception as e:
        _log.error(f"[PATCH ERR] {path} | {e}")


def patch_gif_trailing_byte(path: str, value: int = 0x21):
    """GIF'in son byte'ını Steam patch değeriyle değiştirir."""
    try:
        with open(path, "rb") as f:
            data = bytearray(f.read())
        if not data:
            return
        if data[-1] == value:
            _log.info(f"[GIF PATCH] {os.path.basename(path)} zaten 0x{value:02X} ile bitiyor")
            return
        data[-1] = value
        with open(path, "wb") as f:
            f.write(data)
        _log.info(f"[GIF PATCH] {os.path.basename(path)} -> last byte = 0x{value:02X}")
    except Exception as e:
        _log.error(f"[GIF PATCH ERR] {path} | {e}")


def find_gifsicle() -> str | None:
    """Bundled/PATH gifsicle yolunu bulur (hem src hem kök layout için)."""
    found = shutil.which("gifsicle")
    if found:
        return found
    here = os.path.dirname(os.path.abspath(__file__))
    # src/steameditor/core -> proje kökünü bulmak için yukarı çık
    proj_root = os.path.abspath(os.path.join(here, "..", "..", ".."))
    candidates = [
        os.path.join(here, "GIF", "bin", "gifsicle.exe"),
        os.path.join(proj_root, "GIF", "bin", "gifsicle.exe"),
        os.path.join(proj_root, "GIF", "bin", "gifsicle"),
        os.path.join(proj_root, "src", "steameditor", "resources", "GIF_bin", "gifsicle.exe"),
        os.path.join(proj_root, "src", "steameditor", "resources", "GIF_bin", "gifsicle"),
        os.path.join(here, "bin", "gifsicle.exe"),
    ]
    return next((p for p in candidates if os.path.isfile(p)), None)


GIFSICLE_PATH = find_gifsicle()


def optimize_gif_file(path: str, lossy: int = 80, colors: int = 128) -> bool:
    """Split sonrası GIF'i tekrar optimize eder; başarısız olursa orijinali bırakır."""
    if not GIFSICLE_PATH or not os.path.isfile(path):
        return False
    tmp = path + ".opt.gif"
    try:
        before = os.path.getsize(path)
        cmd = [
            GIFSICLE_PATH,
            f"--lossy={lossy}",
            f"--colors={colors}",
            "-O3",
            path,
            "-o",
            tmp,
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, creationflags=_NO_WINDOW)
        after = os.path.getsize(tmp)
        if after > 0 and after < before:
            os.replace(tmp, path)
            _log.info(f"[GIF OPT] {os.path.basename(path)} {before/1024/1024:.1f}MB -> {after/1024/1024:.1f}MB")
            return True
        try:
            os.remove(tmp)
        except Exception:
            pass
    except Exception as e:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        _log.error(f"[GIF OPT ERR] {os.path.basename(path)} | {e}")
    return False


def _resolve_border_dir() -> str:
    """Border Templates klasörünü bul (src/resources, kök, legacy)."""
    here = os.path.dirname(os.path.abspath(__file__))
    proj_root = os.path.abspath(os.path.join(here, "..", "..", ".."))
    candidates = [
        os.path.join(proj_root, "src", "steameditor", "resources", "border_templates"),
        os.path.join(proj_root, "Border Templates"),
        os.path.join(here, "Border Templates"),
        os.path.join(here, "..", "resources", "border_templates"),
    ]
    for c in candidates:
        if os.path.isdir(c):
            return c
    # Fallback: ilk aday (yoksa list_border_templates boş döner)
    return candidates[0]

_BORDER_DIR = _resolve_border_dir()


# ==========================================================
#   Yardımcı: Cover Resize (oranı bozmadan kırpma)
# ==========================================================

def _autocrop_bbox(img: Image.Image, tolerance: int = 12):
    """Görselin etrafındaki 'boş' kenarın içindeki gerçek içerik kutusunu döner.
    Şeffaf kenar varsa alpha kanalından; yoksa sol-üst köşe rengi arka plan
    kabul edilip ondan tolerance kadar sapan pikseller içerik sayılır."""
    rgba = img.convert("RGBA")
    alpha = rgba.getchannel("A")
    if alpha.getextrema()[0] < 250:
        return alpha.point(lambda a: 255 if a > 8 else 0).getbbox()
    rgb = rgba.convert("RGB")
    corner = rgb.getpixel((0, 0))
    bg = Image.new("RGB", rgb.size, corner)
    diff = ImageChops.difference(rgb, bg).convert("L")
    return diff.point(lambda p: 255 if p > tolerance else 0).getbbox()


def autocrop_borders(img: Image.Image, cfg: dict | None) -> Image.Image:
    """cfg'de autocrop_enabled açıksa etraftaki şeffaf/tek renk boşluğu kırpar
    (ezgif'in 'trim transparent pixels' seçeneğinin karşılığı). Tamamen boş
    (bbox=None) veya zaten sıfır kenarlı görsellerde no-op."""
    if not cfg or not bool(cfg.get("autocrop_enabled", False)):
        return img
    try:
        bbox = _autocrop_bbox(img)
        if bbox and bbox != (0, 0, img.width, img.height):
            _log.info(f"[AUTOCROP] {img.width}x{img.height} -> "
                      f"{bbox[2]-bbox[0]}x{bbox[3]-bbox[1]}")
            return img.crop(bbox)
    except Exception as e:
        _log.error(f"[AUTOCROP ERR] {e}")
    return img


def save_output_piece(piece: Image.Image, outdir: str, stem: str,
                      cfg: dict | None, patch: bool) -> str:
    """Parçayı cfg'deki çıktı formatı/kalitesiyle kaydeder, tam yolu döner.
    stem: uzantısız dosya adı. JPG seçiliyse RGB'ye çevrilip quality ile
    yazılır ve son-byte patch UYGULANMAZ (Workshop hilesi PNG'ye özgü;
    JPG'nin son byte'ı bozulursa görüntüleyiciler dosyayı reddedebilir)."""
    fmt = str((cfg or {}).get("output_format", "png")).lower()
    if fmt == "jpg":
        full = os.path.join(outdir, stem + ".jpg")
        raw_q = (cfg or {}).get("jpg_quality", 90)
        if raw_q is None:
            raw_q = 90
        quality = max(1, min(100, int(raw_q)))
        piece.convert("RGB").save(full, quality=quality, optimize=True)
        if patch:
            _log.info(f"[PATCH SKIP] JPG çıktısında son-byte patch atlandı: {stem}.jpg")
        return full
    full = os.path.join(outdir, stem + ".png")
    piece.save(full)
    if patch:
        patch_png_last_byte(full)
    return full


def uniform_slice_bounds(total_w: int, parts: int) -> list[tuple[int, int]]:
    """Uniform şablonda dikey kesim sınırları [(x1,x2),...]. Kalan pikseller
    İLK parçalara +1px olarak dağıtılır — Steam vitrini akışının beklediği
    düzen: 754/5 -> 151,151,151,151,150 (kesim noktaları 151-302-453-604,
    kullanıcının elle doğrulanmış notlarıyla birebir). Eskiden kalan SON
    parçaya yığılıyordu (150,150,150,150,154) ve vitrinde hiza kaydırıyordu."""
    parts = max(1, int(parts))
    base = total_w // parts
    rem = total_w % parts
    bounds = []
    x = 0
    for i in range(parts):
        w = base + (1 if i < rem else 0)
        bounds.append((x, x + w))
        x += w
    return bounds


def resize_cover(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """
    Görseli oranı bozmadan hedef alanı tamamen dolduracak şekilde büyüt,
    sonra ortadan kırp. (Instagram cover mantığı)
    """
    w, h = img.size
    if w == 0 or h == 0:
        return img

    scale = max(target_w / w, target_h / h)
    new_w = int(w * scale)
    new_h = int(h * scale)

    img = img.resize((new_w, new_h), Image.LANCZOS)

    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    right = left + target_w
    bottom = top + target_h

    return img.crop((left, top, right, bottom))


def list_border_templates() -> list[str]:
    if not os.path.isdir(_BORDER_DIR):
        return []
    exts = (".png", ".webp", ".jpg", ".jpeg")
    return sorted(
        f for f in os.listdir(_BORDER_DIR)
        if f.lower().endswith(exts) and os.path.isfile(os.path.join(_BORDER_DIR, f))
    )


def _parse_hex_color(value: str, fallback=(139, 92, 246)) -> tuple[int, int, int]:
    text = (value or "").strip().lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        return fallback
    try:
        return tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return fallback


def _parse_int_safe(value, default: int) -> int:
    """Int değeri güvenli parse eder; None veya parse edilemezse default'a düşer.
    Buradaki kritik nüans: `value or default` yapsaydık gerçek 0 değeri de
    default'a dönerdi (kullanıcı opacity/size'ı 0'a çekince). Burada None
    olan 'yok' demek, 0 olan 'kasıtlı sıfır' demek."""
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _border_cfg_enabled(cfg: dict | None) -> bool:
    if not cfg or not bool(cfg.get("border_fx_enabled", False)):
        return False
    name = cfg.get("border_fx_template", "")
    return bool(name and os.path.isfile(os.path.join(_BORDER_DIR, name)))


_BORDER_CACHE: dict[tuple[str, tuple[int, int]], Image.Image] = {}
_BORDER_CACHE_MAX = 8


def _get_cached_border(path: str, size: tuple[int, int]) -> Image.Image:
    key = (path, size)
    cached = _BORDER_CACHE.get(key)
    if cached is not None:
        return cached
    # Load and resize, cache with LRU eviction
    img = Image.open(path).convert("RGBA").resize(size, Image.LANCZOS)
    if len(_BORDER_CACHE) >= _BORDER_CACHE_MAX:
        # Remove oldest (first inserted)
        _BORDER_CACHE.pop(next(iter(_BORDER_CACHE)))
    _BORDER_CACHE[key] = img
    return img


def apply_border_fx(img: Image.Image, cfg: dict | None) -> Image.Image:
    """Border Templates içindeki PNG'yi görselin üstüne renk/glow ile bindirir."""
    if not _border_cfg_enabled(cfg):
        return img

    path = os.path.join(_BORDER_DIR, cfg.get("border_fx_template", ""))
    try:
        base = img.convert("RGBA")
        border = _get_cached_border(path, base.size)
        opacity = max(0, min(100, _parse_int_safe(cfg.get("border_fx_opacity"), 100))) / 100.0
        glow = max(0, min(100, _parse_int_safe(cfg.get("border_fx_glow"), 0))) / 100.0
        color = _parse_hex_color(cfg.get("border_fx_color", "#8B5CF6"))

        alpha = border.getchannel("A")
        if opacity < 1.0:
            alpha = alpha.point(lambda p: int(p * opacity))

        colored = Image.new("RGBA", base.size, color + (0,))
        colored.putalpha(alpha)

        if glow > 0:
            glow_alpha = alpha.filter(ImageFilter.GaussianBlur(max(2, int(18 * glow))))
            glow_alpha = glow_alpha.point(lambda p: int(p * min(1.0, 0.35 + glow * 0.65)))
            glow_layer = Image.new("RGBA", base.size, color + (0,))
            glow_layer.putalpha(glow_alpha)
            base = Image.alpha_composite(base, glow_layer)

        return Image.alpha_composite(base, colored)
    except Exception as e:
        _log.error(f"[BORDER FX ERR] {path} | {e}")
        return img


def apply_auto_enhance(img: Image.Image, cfg: dict | None) -> Image.Image:
    """Otomatik kontrast/doygunluk/parlaklık/keskinlik iyileştirmesi.
    Kırpma/border/metin katmanlarından ÖNCE, tüm canvas'a tek seferde uygulanır
    (parçalar ayrı ayrı iyileştirilirse her biri farklı histogram alıp
    Workshop parçaları arasında renk uyumsuzluğuna yol açardı)."""
    if not cfg or not bool(cfg.get("auto_enhance_enabled", False)):
        return img
    intensity = max(0, min(100, _parse_int_safe(cfg.get("auto_enhance_intensity"), 50))) / 100.0
    if intensity <= 0:
        return img
    try:
        base = img.convert("RGBA")
        rgb = ImageOps.autocontrast(base.convert("RGB"), cutoff=1)
        rgb = ImageEnhance.Color(rgb).enhance(1.0 + 0.25 * intensity)
        rgb = ImageEnhance.Contrast(rgb).enhance(1.0 + 0.12 * intensity)
        rgb = ImageEnhance.Brightness(rgb).enhance(1.0 + 0.05 * intensity)
        rgb = ImageEnhance.Sharpness(rgb).enhance(1.0 + 0.15 * intensity)
        out = rgb.convert("RGBA")
        out.putalpha(base.getchannel("A"))
        return out
    except Exception as e:
        _log.error(f"[AUTO ENHANCE ERR] {e}")
        return img


_OVERLAY_FONT_CACHE: dict[int, "ImageFont.FreeTypeFont"] = {}
_OVERLAY_FONT_CANDIDATES = (
    # Windows
    r"C:\Windows\Fonts\seguisb.ttf",
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    # macOS
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    # Linux (Debian/Ubuntu/Arch)
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/arial.ttf",
    # Flatpak / Snap
    "/app/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)


def _load_overlay_font(size: int):
    size = max(8, int(size))
    cached = _OVERLAY_FONT_CACHE.get(size)
    if cached:
        return cached
    font = None
    for path in _OVERLAY_FONT_CANDIDATES:
        if os.path.isfile(path):
            try:
                font = ImageFont.truetype(path, size)
                break
            except Exception:
                continue
    # Fallback: scan common font dirs for any TTF
    if font is None:
        import glob
        fallback_globs = [
            "/usr/share/fonts/**/*.ttf",
            "/usr/local/share/fonts/**/*.ttf",
            "/System/Library/Fonts/**/*.ttf",
            "/Library/Fonts/**/*.ttf",
        ]
        for pattern in fallback_globs:
            for cand in glob.glob(pattern, recursive=True):
                try:
                    font = ImageFont.truetype(cand, size)
                    _log.info(f"[FONT] Fallback font found: {cand}")
                    break
                except Exception:
                    continue
            if font:
                break
    if font is None:
        font = ImageFont.load_default()
    _OVERLAY_FONT_CACHE[size] = font
    return font


_TEXT_OVERLAY_POSITIONS = (
    "Üst Sol", "Üst Orta", "Üst Sağ",
    "Alt Sol", "Alt Orta", "Alt Sağ",
    "Orta",
)


def _text_overlay_geometry(size: tuple[int, int], cfg: dict):
    """Metin katmanının (W,H) canvas'taki yerleşimini TEK yerde hesaplar:
    (text, font, bbox, x, y, tw, th) döner; metin yoksa None.
    text_overlay_custom_pos ([x_pct, y_pct], 0..1) varsa isimli konumu ezer —
    kullanıcı metni önizlemede sürükleyerek serbest yerleştirmiş demektir."""
    text = (cfg.get("text_overlay_text") or "").strip()
    if not text:
        return None
    W, H = size
    size_pct = max(1, min(30, _parse_int_safe(cfg.get("text_overlay_size"), 6)))
    font_size = max(10, int(H * size_pct / 100))
    font = _load_overlay_font(font_size)

    dummy = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = dummy.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    margin = max(8, int(W * 0.03))

    custom = cfg.get("text_overlay_custom_pos")
    if isinstance(custom, (list, tuple)) and len(custom) == 2:
        x = int(float(custom[0]) * max(1, W - tw))
        y = int(float(custom[1]) * max(1, H - th))
        x = max(0, min(max(0, W - tw), x))
        y = max(0, min(max(0, H - th), y))
    else:
        positions = {
            "Üst Sol": (margin, margin),
            "Üst Orta": ((W - tw) // 2, margin),
            "Üst Sağ": (W - tw - margin, margin),
            "Alt Sol": (margin, H - th - margin),
            "Alt Orta": ((W - tw) // 2, H - th - margin),
            "Alt Sağ": (W - tw - margin, H - th - margin),
            "Orta": ((W - tw) // 2, (H - th) // 2),
        }
        x, y = positions.get(cfg.get("text_overlay_position", "Alt Orta"), positions["Alt Orta"])
    return text, font, bbox, x, y, tw, th


def text_overlay_bbox(size: tuple[int, int], cfg: dict | None):
    """Metnin (W,H) canvas'taki kutusu (x1,y1,x2,y2) — hit-test/sürükleme için.
    Metin kapalı/boşsa None."""
    if not cfg or not bool(cfg.get("text_overlay_enabled", False)):
        return None
    geo = _text_overlay_geometry(size, cfg)
    if geo is None:
        return None
    _text, _font, _bbox, x, y, tw, th = geo
    return (x, y, x + tw, y + th)


def apply_text_overlay(img: Image.Image, cfg: dict | None) -> Image.Image:
    """Görselin üstüne başlık/imza metni bindirir (border FX'ten sonra, en üstte).
    Uniform şablonlarda tüm canvas'a tek seferde uygulanır; Workshop parçaları
    yan yana dizilince metin de Border FX gibi bütün olarak birleşir.
    Konum yüzde tabanlı hesaplandığı için aynı cfg, küçültülmüş önizleme
    kopyasında da orantılı olarak aynı yere düşer (canlı sürükleme bundan
    yararlanır)."""
    if not cfg or not bool(cfg.get("text_overlay_enabled", False)):
        return img
    geo = _text_overlay_geometry(img.size, cfg)
    if geo is None:
        return img
    try:
        text, font, bbox, x, y, _tw, _th = geo
        base = img.convert("RGBA")
        layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)

        color = _parse_hex_color(cfg.get("text_overlay_color", "#FFFFFF"), (255, 255, 255))
        opacity = max(0, min(100, _parse_int_safe(cfg.get("text_overlay_opacity"), 100))) / 100.0
        alpha = int(255 * opacity)

        x -= bbox[0]
        y -= bbox[1]

        # Okunabilirlik için ince koyu kontur
        shadow_alpha = int(alpha * 0.75)
        for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, -2), (-2, 2), (2, 2)):
            draw.text((x + ox, y + oy), text, font=font, fill=(0, 0, 0, shadow_alpha))
        draw.text((x, y), text, font=font, fill=color + (alpha,))

        return Image.alpha_composite(base, layer)
    except Exception as e:
        _log.error(f"[TEXT OVERLAY ERR] {e}")
        return img


def _apply_effects_pipeline(img: Image.Image, cfg: dict | None) -> Image.Image:
    """Tüm canvas'a tek seferde: otomatik iyileştir -> border FX -> metin katmanı.
    Sıra önemli: iyileştirme kırpmadan önce (parçalar arası renk tutarlılığı),
    metin en üstte (border glow'un altında kalmasın)."""
    img = apply_auto_enhance(img, cfg)
    img = apply_border_fx(img, cfg)
    img = apply_text_overlay(img, cfg)
    return img


def _template_preview_canvas(img: Image.Image, template: dict,
                             band_count: int = 1) -> tuple[Image.Image, list[tuple[int, int, int, int]]]:
    """Şablonun kullanacağı canvas'ı ve parça kutularını üretir.
    band_count > 1 (sadece uniform): kaynak NATIVE çözünürlükte bırakılır,
    üst-orta başlangıçtan aşağıya doğru sığdığı kadar bant grid'i çizilir —
    "Konumu Seç, Gerisini Otomatik Böl" akışının varsayılan yerleşimini gösterir."""
    img = img.convert("RGBA")
    mode = template["mode"]

    if mode == "uniform":
        target_w = template["width"]
        target_h = template["height"]
        parts = template["parts"]
        bounds = uniform_slice_bounds(target_w, parts)

        if band_count > 1:
            # Çoklu bant: canvas = kaynağın kendisi (native), kutular üst-orta
            # başlangıçlı bant grid'i. Manuel crop da native pikselden keser.
            w, h = img.size
            x0 = max(0, (w - target_w) // 2)
            full_bands = min(band_count, h // target_h) if target_h else 0
            boxes = []
            for band in range(max(1, full_bands)):
                y1 = band * target_h
                for bx1, bx2 in bounds:
                    boxes.append((x0 + bx1, y1, x0 + bx2, y1 + target_h))
            return img, boxes

        # Tek bant: sabit target_w x target_h canvas'a cover-crop
        # (multi/single ile tutarlı) — kaynağın kendi oranına göre değil.
        canvas = resize_cover(img, target_w, target_h)
        boxes = [(x1, 0, x2, target_h) for x1, x2 in bounds]
        return canvas, boxes

    if mode == "multi":
        parts_def = template["parts"]
        total_w = sum(p["width"] for p in parts_def)
        max_h = max(p["height"] for p in parts_def)
        canvas = resize_cover(img, total_w, max_h)
        boxes = []
        cur_x = 0
        for part in parts_def:
            pw, ph = part["width"], part["height"]
            boxes.append((cur_x, 0, cur_x + pw, ph))
            cur_x += pw
        return canvas, boxes

    tw = template["width"]
    th = template["height"]
    return resize_cover(img, tw, th), [(0, 0, tw, th)]


def _load_gif_frames(path: str):
    """GIF’in tüm frame ve sürelerini döner: (frames_rgba, durations)."""
    gif = Image.open(path)
    frames, durations = [], []
    for frame in ImageSequence.Iterator(gif):
        frames.append(frame.convert("RGBA"))
        durations.append(frame.info.get("duration", 40))
    return frames, durations


def _save_animated_gif(frames_rgba, durations, outpath: str, patch: bool = False):
    """RGBA frame listesini animasyonlu GIF olarak kaydeder.
    Şeffaflık varsa korunur; aksi halde saydam/glow alanları siyaha dönerdi.
    patch=True ise dosyaya yazıldıktan SONRA trailing byte `0x21`'e çekilir
    (gifsicle optimize AŞAMASINDAN ÖNCE uygulanırsa boyutu büyür, sonra da
    gifsicle'in son byte'ı ezme riski var — sıralama çağıranın sorumluluğunda;
    mevcut çağrılarda optimize->patch olarak işletilir)."""
    rgba_frames = [f.convert("RGBA") for f in frames_rgba]
    has_alpha = any(fr.getchannel("A").getextrema()[0] < 250 for fr in rgba_frames)

    if has_alpha:
        out_frames = []
        for fr in rgba_frames:
            p = fr.convert("RGB").convert("P", palette=Image.ADAPTIVE, colors=255)
            # Saydam pikselleri 255. palet indeksine ata
            transparent_mask = fr.getchannel("A").point(lambda a: 255 if a < 128 else 0)
            p.paste(255, transparent_mask)
            out_frames.append(p)
        out_frames[0].save(
            outpath, save_all=True, append_images=out_frames[1:],
            duration=durations, loop=0, disposal=2, transparency=255,
        )
    else:
        out_frames = [fr.convert("RGB").convert("P", palette=Image.ADAPTIVE) for fr in rgba_frames]
        out_frames[0].save(
            outpath, save_all=True, append_images=out_frames[1:],
            duration=durations, loop=0, disposal=2,
        )
    if patch:
        patch_gif_trailing_byte(outpath)


def split_gif_frames(path: str, outdir: str, template: dict, cfg: dict | None = None,
                     name_override: str | None = None,
                     preset_origin: tuple[int, int] | None = None,
                     region_scale: float = 1.0, band_count: int = 1):
    """
    Animasyonlu GIF’i frame-by-frame split eder.
    uniform, multi ve single modların tamamında animasyonlu GIF üretir.
    name_override verilirse çıktı adı kaynak dosya adı yerine bunu kullanır
    (toplu işlemde aynı isimli farklı kaynakların üstüne yazmasını önlemek için).
    preset_origin verilirse (uniform): interaktif grid'in konumundan NATIVE
    kesim yapılır — kaynak cover-crop ile büyütülmez/kırpılmaz; bölge
    (region_scale ile seçilmişse) şablon boyutuna ölçeklenir ve dilimlenir.
    Statik görsellerdeki grid akışıyla birebir aynı davranış.
    """
    os.makedirs(outdir, exist_ok=True)
    created_files = []

    base = name_override or os.path.splitext(os.path.basename(path))[0]
    prefix = template.get("prefix", "parca")
    mode = template["mode"]

    frames, durations = _load_gif_frames(path)
    if not frames:
        return created_files

    # Autocrop: bbox İLK kareden hesaplanır ve TÜM karelere aynı uygulanır —
    # kare kare hesaplansaydı içerik hareket ettikçe boyut değişip titrerdi.
    if cfg and bool(cfg.get("autocrop_enabled", False)):
        try:
            bbox = _autocrop_bbox(frames[0])
            if bbox and bbox != (0, 0, frames[0].width, frames[0].height):
                frames = [f.crop(bbox) for f in frames]
        except Exception as e:
            _log.error(f"[AUTOCROP GIF ERR] {e}")

    # GIF optimizasyon gücü ayarlanabilir (Ayarlar > Genel > Çıktı)
    raw_lossy = (cfg or {}).get("gif_lossy", 80)
    raw_colors = (cfg or {}).get("gif_colors", 128)
    gif_lossy = max(0, min(200, int(raw_lossy if raw_lossy is not None else 80)))
    gif_colors = max(2, min(256, int(raw_colors if raw_colors is not None else 128)))

    # -------------------------------------------------------
    # MODE: UNIFORM
    # -------------------------------------------------------
    if mode == "uniform":
        target_w = template["width"]
        target_h = template["height"]
        parts = template["parts"]
        bounds = uniform_slice_bounds(target_w, parts)

        if preset_origin is not None:
            # İnteraktif grid yolu: NATIVE kesim (statik akışla birebir).
            # Efektler önce TAM kareye uygulanır (WYSIWYG — önizleme de
            # efekt sonrası tam görsel üstünde çiziliyor).
            rs = max(0.05, float(region_scale))
            bands_eff = max(1, band_count)
            gw = int(round(target_w * rs))
            gh = int(round(target_h * bands_eff * rs))
            W, H = frames[0].size
            bx = max(0, min(W - gw, int(preset_origin[0])))
            by = max(0, min(H - gh, int(preset_origin[1])))
            target_size = (target_w, target_h * bands_eff)

            regions = []
            for f in frames:
                f = _apply_effects_pipeline(f, cfg)
                r = f.crop((bx, by, bx + gw, by + gh))
                if r.size != target_size:
                    r = r.resize(target_size, Image.LANCZOS)
                regions.append(r)

            idx = 1
            for band in range(bands_eff):
                y1 = band * target_h
                for x1, x2 in bounds:
                    part_frames = [r.crop((x1, y1, x2, y1 + target_h)) for r in regions]
                    outpath = os.path.join(outdir, f"{prefix}_{base}_{idx:02}.gif")
                    _save_animated_gif(part_frames, durations, outpath, False)
                    optimize_gif_file(outpath, gif_lossy, gif_colors)
                    if template.get("patch", False):
                        patch_gif_trailing_byte(outpath)
                    created_files.append(outpath)
                    idx += 1
            _log.info(f"[GIF SPLIT] {os.path.basename(path)} -> {len(created_files)} "
                      f"animasyonlu parca (grid: {bx},{by} · %{round(rs*100)})")
            return created_files

        # Sabit target_w x target_h canvas'a cover-crop — process_image
        # ve multi/single modlarıyla tutarlı (bkz. resize_cover).
        scaled = [_apply_effects_pipeline(resize_cover(f, target_w, target_h), cfg) for f in frames]

        for i, (x1, x2) in enumerate(bounds):
            part_frames = [fr.crop((x1, 0, x2, target_h)) for fr in scaled]
            outpath = os.path.join(outdir, f"{prefix}_{base}_{i+1:02}.gif")
            _save_animated_gif(part_frames, durations, outpath, False)
            optimize_gif_file(outpath, gif_lossy, gif_colors)
            if template.get("patch", False):
                patch_gif_trailing_byte(outpath)
            created_files.append(outpath)

    # -------------------------------------------------------
    # MODE: MULTI
    # -------------------------------------------------------
    elif mode == "multi":
        parts_def = template["parts"]
        total_w = sum(p["width"] for p in parts_def)
        max_h   = max(p["height"] for p in parts_def)

        # Tüm frameleri cover-resize ile ortak canvas’a oturt
        scaled = [_apply_effects_pipeline(resize_cover(f, total_w, max_h), cfg) for f in frames]

        cur_x = 0
        for idx, part in enumerate(parts_def, start=1):
            pw, ph = part["width"], part["height"]
            part_frames = [fr.crop((cur_x, 0, cur_x + pw, ph)) for fr in scaled]
            outpath = os.path.join(outdir, f"{prefix}_{base}_{idx:02}.gif")
            _save_animated_gif(part_frames, durations, outpath, False)
            optimize_gif_file(outpath, gif_lossy, gif_colors)
            created_files.append(outpath)
            cur_x += pw

    # -------------------------------------------------------
    # MODE: SINGLE
    # -------------------------------------------------------
    elif mode == "single":
        tw = template["width"]
        th = template["height"]
        scaled = [_apply_effects_pipeline(resize_cover(f, tw, th), cfg) for f in frames]
        outpath = os.path.join(outdir, f"{prefix}_{base}.gif")
        _save_animated_gif(scaled, durations, outpath, False)
        optimize_gif_file(outpath, gif_lossy, gif_colors)
        created_files.append(outpath)

    _log.info(f"[GIF SPLIT] {os.path.basename(path)} -> {len(created_files)} animasyonlu parca ({mode})")
    return created_files


# ==========================================================
#   MOTOR – OTOMATİK PRESET MODU
# ==========================================================

def process_image(path: str, outdir: str, template: dict, cfg: dict | None = None,
                  name_override: str | None = None):
    """
    Otomatik mod: presetlere göre crop + (gerekirse) patch.
    GÜNCELLEME: GIF ise animasyonlu split motoru devreye girer.
    name_override verilirse çıktı adı kaynak dosya adı yerine bunu kullanır
    (toplu işlemde aynı isimli farklı kaynakların üstüne yazmasını önlemek için).
    """
    # GIF ise özel animasyonlu splitter
    if path.lower().endswith(".gif"):
        return split_gif_frames(path, outdir, template, cfg, name_override=name_override)

    os.makedirs(outdir, exist_ok=True)
    created = []

    base = name_override or os.path.splitext(os.path.basename(path))[0]
    prefix = template.get("prefix", "parca")
    mode = template["mode"]

    original = Image.open(path).convert("RGBA")
    original = autocrop_borders(original, cfg)

    # -------------------------------
    # MODE: UNIFORM (Workshop 5'li) - SABİT CANVAS (cover-crop)
    # -------------------------------
    if mode == "uniform":
        target_w = template["width"]   # Genelde 750px (5x150)
        target_h = template["height"]  # Genelde 1250px
        parts = template["parts"]

        # Sabit target_w x target_h canvas'a oranı bozmadan KIRPARAK (cover)
        # otur — kaynağın kendi en-boy oranına göre "dinamik" yükseklik
        # DEĞİL. Aksi halde geniş/dar oranlı kaynaklarda çoğu parça boş/
        # karanlık kenara düşüyordu (bkz. steam_splitter_presets.json'daki
        # "Steam 150x1250 (5)" preseti: height=1250 kayıtlı ama eskiden
        # hiç kullanılmıyordu).
        img = _apply_effects_pipeline(resize_cover(original, target_w, target_h), cfg)

        for i, (x1, x2) in enumerate(uniform_slice_bounds(target_w, parts)):
            piece = img.crop((x1, 0, x2, target_h))
            full = save_output_piece(piece, outdir, f"{prefix}_{base}_{i+1:02}",
                                     cfg, bool(template.get("patch")))
            created.append(full)

    # -------------------------------
    # MODE: MULTI (Çizim vitrini 2'li)
    # -------------------------------
    elif mode == "multi":
        total_w = sum(p["width"] for p in template["parts"])
        max_h = max(p["height"] for p in template["parts"])

        base_img = _apply_effects_pipeline(resize_cover(original, total_w, max_h), cfg)

        cur_x = 0
        index = 1
        for part in template["parts"]:
            pw = part["width"]
            ph = part["height"]

            piece = base_img.crop((cur_x, 0, cur_x + pw, ph))
            full = save_output_piece(piece, outdir, f"{prefix}_{base}_{index:02}",
                                     cfg, False)
            created.append(full)
            index += 1
            cur_x += pw

    # -------------------------------
    # MODE: SINGLE (Screenshot)
    # -------------------------------
    elif mode == "single":
        w = template["width"]
        h = template["height"]
        piece = _apply_effects_pipeline(resize_cover(original, w, h), cfg)
        full = save_output_piece(piece, outdir, f"{prefix}_{base}",
                                 cfg, bool(template.get("patch")))
        created.append(full)

    return created


def process_folder(folder: str, outdir: str, template: dict, cfg: dict | None = None):
    created = []
    for f in os.listdir(folder):
        if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
            created.extend(
                process_image(os.path.join(folder, f), outdir, template, cfg)
            )
    return created

# ==========================================================
#   MANUAL CROP WITH TEMPLATE (interactive grid)
# ==========================================================

def manual_crop_with_template(master, img_path: str, outdir: str, template: dict, cfg: dict | None = None,
                               band_count: int = 1, preset_origin: tuple[int, int] | None = None,
                               region_scale: float = 1.0) -> list[str]:
    """
    Manuel crop modu:
    - Kullanıcı sadece İLK bandın İLK parçasının alanını (başlangıç
      pozisyonunu) seçer — tıpkı ezgif'te elle yaptığı gibi.
    - Diğer parçalar aynı bant içinde şablon genişliklerine göre sağa
      doğru otomatik kesilir.
    - `band_count` > 1 ve şablon 'uniform' ise, seçilen başlangıç konumundan
      aşağıya doğru (her biri template height kadar) toplam band_count adet
      bağımsız bant daha otomatik üretilir (kaynağın boyu yetmediği yerde
      sessizce durur, kısmi/gerilmiş bant üretilmez).
    - `preset_origin` verilirse dialog HİÇ açılmaz — konum ana önizlemedeki
      sürüklenebilir grid'den gelir (bkz. App._setup_interactive_preview);
      bu yol saf PIL olduğundan worker thread'de de çağrılabilir.
    """
    os.makedirs(outdir, exist_ok=True)
    base = os.path.splitext(os.path.basename(img_path))[0]
    prefix = template.get("prefix", "parca")
    mode = template["mode"]

    # GIF ise burada animasyonlu işlemek istemiyoruz, uyarı verip çıkalım
    if img_path.lower().endswith(".gif"):
        from tkinter import messagebox
        messagebox.showinfo("Bilgi", "Manuel crop şu an sadece statik görsellerde aktif. GIF için otomatik bölme kullan.")
        return []

    # Tüm parçaları tek listede tut — genişlikler uniform_slice_bounds'tan
    # (754/5 -> 151,151,151,151,150; kalan px İLK parçalara dağıtılır)
    if mode == "uniform":
        ph = template["height"]  # sabit — otomatik Böl ile tutarlı (cover-crop)
        parts_info = [{"width": x2 - x1, "height": ph}
                      for x1, x2 in uniform_slice_bounds(template["width"], template["parts"])]
        band_h = template["height"]
    else:
        # Çoklu bant kavramı sadece 'uniform' (eşit parçalı) şablonlarda
        # anlamlı; diğer modlarda tek bant gibi davran.
        band_count = 1
        band_h = 0
        if mode == "multi":
            parts_info = template["parts"]
        else:  # single
            parts_info = [{"width": template["width"], "height": template["height"]}]

    img = Image.open(img_path).convert("RGBA")
    img = autocrop_borders(img, cfg)
    img = _apply_effects_pipeline(img, cfg)
    img_w, img_h = img.size

    # Sadece ilk bandın ilk parçası için kullanıcıdan seçim al
    first = parts_info[0]
    tw = first["width"]
    th = first["height"]
    if preset_origin is not None and mode == "uniform":
        # İnteraktif grid yolu: seçilen bölge (region_scale ile büyütülmüş/
        # küçültülmüş olabilir) TEK seferde kırpılır, şablonun gerçek
        # boyutuna ölçeklenir ve dilimlere ayrılır. rs=1.0'da resize no-op.
        rs = max(0.05, float(region_scale))
        tw_total = template["width"]
        bands_eff = max(1, band_count)
        gw = int(round(tw_total * rs))
        gh = int(round(band_h * bands_eff * rs))
        bx = max(0, min(img_w - gw, int(preset_origin[0])))
        by = max(0, min(img_h - gh, int(preset_origin[1])))
        region = img.crop((bx, by, bx + gw, by + gh))
        target_size = (tw_total, band_h * bands_eff)
        if region.size != target_size:
            region = region.resize(target_size, Image.LANCZOS)

        created = []
        idx = 1
        for band in range(bands_eff):
            y1 = band * band_h
            for x1, x2 in uniform_slice_bounds(tw_total, len(parts_info)):
                piece = region.crop((x1, y1, x2, y1 + band_h))
                full = save_output_piece(piece, outdir, f"{prefix}_{base}_{idx:02}",
                                          cfg, bool(template.get("patch")))
                created.append(full)
                idx += 1
        return created

    if preset_origin is not None:
        base_x = max(0, min(img_w - tw, int(preset_origin[0])))
        base_y = max(0, min(img_h - th, int(preset_origin[1])))
    else:
        if band_count > 1:
            title = (f"Başlangıç (1. Bant) - {tw}x{th} alanını seç — aşağıya doğru "
                     f"{band_count} bant otomatik devam edecek (ENTER ile onayla)")
        else:
            title = f"Başlangıç - {tw}x{th} alanını seç (ENTER ile onayla)"
        # UI diyaloğu lazy import edilir (core katmanı UI'a bağımlı kalmaz)
        from steameditor.ui.components import FixedCropDialog
        dlg = FixedCropDialog(master, img, tw, th, title=title)
        bbox = dlg.get_bbox()
        if not bbox:
            return []
        x1, y1, x2, y2 = bbox
        base_x = x1
        base_y = y1

    created = []
    idx = 1

    for band in range(max(1, band_count)):
        band_y = base_y + band * band_h
        # Otomatik devam eden bantlar (ilk banttan sonrakiler) kaynağa tam
        # sığmıyorsa kısmi/gerilmiş bant üretmeden sessizce dur.
        if band > 0 and band_y + band_h > img_h:
            break

        cur_x = base_x
        for part in parts_info:
            pw = part["width"]
            ph = part["height"]

            px1 = cur_x
            py1 = band_y

            # Taşma kontrolü (sağ kenar / alt kenar) — sadece ilk bant için,
            # kullanıcının kendi seçtiği konumu makul ölçüde tolere eder.
            if px1 + pw > img_w:
                px1 = max(0, img_w - pw)
            if py1 + ph > img_h:
                py1 = max(0, img_h - ph)

            px2 = px1 + pw
            py2 = py1 + ph

            piece = img.crop((px1, py1, px2, py2))
            full = save_output_piece(piece, outdir, f"{prefix}_{base}_{idx:02}",
                                      cfg, bool(template.get("patch")))
            created.append(full)
            idx += 1
            cur_x += pw  # sonraki parçayı sağa kaydır

    return created


# ==========================================================
#   PREVIEW & SHOWCASE UTILITIES
# ==========================================================

def _template_preview_canvas(img: Image.Image, template: dict,
                              band_count: int = 1) -> tuple[Image.Image, list[tuple[int, int, int, int]]]:
    """Şablonun kullanacağı canvas'ı ve parça kutularını üretir.
    band_count > 1 (sadece uniform): kaynak NATIVE çözünürlükte bırakılır,
    üst-orta başlangıçtan aşağıya doğru sığdığı kadar bant grid'i çizilir —
    "Konumu Seç, Gerisini Otomatik Böl" akışının varsayılan yerleşimini gösterir."""
    img = img.convert("RGBA")
    mode = template["mode"]

    if mode == "uniform":
        target_w = template["width"]
        target_h = template["height"]
        parts = template["parts"]
        bounds = uniform_slice_bounds(target_w, parts)

        if band_count > 1:
            # Çoklu bant: canvas = kaynağın kendisi (native), kutular üst-orta
            # başlangıçlı bant grid'i. Manuel crop da native pikselden keser.
            w, h = img.size
            x0 = max(0, (w - target_w) // 2)
            full_bands = min(band_count, h // target_h) if target_h else 0
            boxes = []
            for band in range(max(1, full_bands)):
                y1 = band * target_h
                for bx1, bx2 in bounds:
                    boxes.append((x0 + bx1, y1, x0 + bx2, y1 + target_h))
            return img, boxes

        # Tek bant: sabit target_w x target_h canvas'a cover-crop
        # (multi/single ile tutarlı) — kaynağın kendi oranına göre değil.
        canvas = resize_cover(img, target_w, target_h)
        boxes = [(x1, 0, x2, target_h) for x1, x2 in bounds]
        return canvas, boxes

    if mode == "multi":
        parts_def = template["parts"]
        total_w = sum(p["width"] for p in parts_def)
        max_h = max(p["height"] for p in parts_def)
        canvas = resize_cover(img, total_w, max_h)
        boxes = []
        cur_x = 0
        for part in parts_def:
            pw, ph = part["width"], part["height"]
            boxes.append((cur_x, 0, cur_x + pw, ph))
            cur_x += pw
        return canvas, boxes

    tw = template["width"]
    th = template["height"]
    return resize_cover(img, tw, th), [(0, 0, tw, th)]


def render_template_preview(img: Image.Image, template: dict, cfg: dict | None = None,
                            band_count: int = 1) -> Image.Image:
    """Bölmeden önce kesim çizgilerini görselin üstüne çizer."""
    canvas, boxes = _template_preview_canvas(img, template, band_count)
    canvas = _apply_effects_pipeline(canvas, cfg)
    multi_band = band_count > 1 and template.get("mode") == "uniform"
    overlay = canvas.copy()
    shade = Image.new("RGBA", overlay.size, (0, 0, 0, 0))
    shade_draw = ImageDraw.Draw(shade)

    for i, box in enumerate(boxes, start=1):
        x1, y1, x2, y2 = box
        fill = (249, 115, 22, 30) if i % 2 else (99, 102, 241, 26)
        shade_draw.rectangle((x1, y1, x2, y2), fill=fill)

    overlay = Image.alpha_composite(overlay, shade)
    draw = ImageDraw.Draw(overlay)
    line_color = (249, 115, 22, 255)
    label_fill = (8, 8, 8, 210)

    for i, box in enumerate(boxes, start=1):
        x1, y1, x2, y2 = box
        draw.rectangle((x1, y1, x2 - 1, y2 - 1), outline=line_color, width=3)
        if i > 1 and not multi_band:
            # Tam-yükseklik dikey çizgi tek bantta anlamlı; çoklu bantta her
            # kutunun kendi çerçevesi grid'i zaten netleştiriyor.
            draw.line((x1, 0, x1, overlay.height), fill=line_color, width=3)
        label = f"#{i}"
        lx = x1 + 8
        ly = y1 + 8
        draw.rounded_rectangle((lx - 4, ly - 3, lx + 34, ly + 19),
                               radius=5, fill=label_fill)
        draw.text((lx, ly), label, fill=(255, 255, 255, 255))

    return overlay


def template_output_summary(img: Image.Image, template: dict, band_count: int = 1) -> str:
    canvas, boxes = _template_preview_canvas(img, template, band_count)
    if not boxes:
        return ""
    first_w = boxes[0][2] - boxes[0][0]
    first_h = boxes[0][3] - boxes[0][1]
    patch = " · patch açık" if template.get("patch") else ""
    parts = template.get("parts")
    if band_count > 1 and template.get("mode") == "uniform" and isinstance(parts, int) and parts:
        bands = len(boxes) // parts
        return (f"{len(boxes)} parça ({bands} bant) · parça {first_w}×{first_h}px"
                f" · kaynak {canvas.width}×{canvas.height}px{patch}")
    return f"{len(boxes)} parça · ilk çıktı {first_w}×{first_h}px · canvas {canvas.width}×{canvas.height}px{patch}"


def render_showcase_preview(piece_paths: list[str], parts_per_row: int = 5,
                            cell_width: int = 116, gap: int = 4,
                            bg_color: tuple[int, int, int] = (23, 26, 33),
                            pad: int = 24) -> Image.Image:
    """Bölünmüş parçaların Steam profil vitrinindeki görünümünü simüle eder:
    koyu profil arka planı + Steam'in parçalar arası boşluklarıyla
    parts_per_row sütunlu grid (çoklu bantta her bant bir satır). Parçalar
    arası boşluğun görsel devamlılığı nerede bozduğu yüklemeden önce görülür.
    GIF parçalarında ilk kare kullanılır."""
    if not piece_paths:
        return Image.new("RGB", (200, 100), bg_color)
    parts_per_row = max(1, int(parts_per_row))

    cells = []
    for path in piece_paths:
        try:
            img = Image.open(path)
            if os.path.splitext(path)[1].lower() == ".gif":
                img.seek(0)
            img = img.convert("RGB")
            scale = cell_width / img.width if img.width else 1.0
            cell = img.resize((cell_width, max(1, int(img.height * scale))), Image.LANCZOS)
        except Exception as e:
            _log.error(f"[SHOWCASE ERR] {path} | {e}")
            cell = Image.new("RGB", (cell_width, cell_width), (60, 60, 60))
        cells.append(cell)

    rows = [cells[i:i + parts_per_row] for i in range(0, len(cells), parts_per_row)]
    row_heights = [max(c.height for c in row) for row in rows]
    canvas_w = pad * 2 + parts_per_row * cell_width + (parts_per_row - 1) * gap
    canvas_h = pad * 2 + sum(row_heights) + (len(rows) - 1) * gap
    canvas = Image.new("RGB", (canvas_w, canvas_h), bg_color)

    y = pad
    for row, rh in zip(rows, row_heights):
        x = pad
        for cell in row:
            canvas.paste(cell, (x, y))
            x += cell_width + gap
        y += rh + gap
    return canvas



# Alias for backward compatibility
apply_effects_pipeline = _apply_effects_pipeline
