"""core.py — Steam Splitter PRO saf işleme katmanı (UI bağımsız).

editor.py bu modülden import eder. Buradaki fonksiyonlar Tkinter'a bağlı
değildir; doğrudan PIL ile çalışır ve headless test edilebilir.
"""
import os
import subprocess
import platform
import shutil

from PIL import Image, ImageSequence, ImageDraw, ImageFilter, ImageFont, ImageOps, ImageEnhance


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
        print(f"[OPEN FOLDER ERR] {e}")


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
        print(f"[PATCH] {os.path.basename(path)} -> last byte = 0x{value:02X}")
    except Exception as e:
        print(f"[PATCH ERR] {path} | {e}")


def patch_gif_trailing_byte(path: str, value: int = 0x21):
    """GIF'in son byte'ını Steam patch değeriyle değiştirir."""
    try:
        with open(path, "rb") as f:
            data = bytearray(f.read())
        if not data:
            return
        if data[-1] == value:
            print(f"[GIF PATCH] {os.path.basename(path)} zaten 0x{value:02X} ile bitiyor")
            return
        data[-1] = value
        with open(path, "wb") as f:
            f.write(data)
        print(f"[GIF PATCH] {os.path.basename(path)} -> last byte = 0x{value:02X}")
    except Exception as e:
        print(f"[GIF PATCH ERR] {path} | {e}")


def find_gifsicle() -> str | None:
    """Bundled/PATH gifsicle yolunu bulur."""
    found = shutil.which("gifsicle")
    if found:
        return found
    root = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(root, "GİF", "bin", "gifsicle.exe"),
        os.path.join(root, "GIF", "bin", "gifsicle.exe"),
        os.path.join(root, "bin", "gifsicle.exe"),
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
            print(f"[GIF OPT] {os.path.basename(path)} {before/1024/1024:.1f}MB -> {after/1024/1024:.1f}MB")
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
        print(f"[GIF OPT ERR] {os.path.basename(path)} | {e}")
    return False


_BORDER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Border Templates")


# ==========================================================
#   Yardımcı: Cover Resize (oranı bozmadan kırpma)
# ==========================================================

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


def _border_cfg_enabled(cfg: dict | None) -> bool:
    if not cfg or not bool(cfg.get("border_fx_enabled", False)):
        return False
    name = cfg.get("border_fx_template", "")
    return bool(name and os.path.isfile(os.path.join(_BORDER_DIR, name)))


def apply_border_fx(img: Image.Image, cfg: dict | None) -> Image.Image:
    """Border Templates içindeki PNG'yi görselin üstüne renk/glow ile bindirir."""
    if not _border_cfg_enabled(cfg):
        return img

    path = os.path.join(_BORDER_DIR, cfg.get("border_fx_template", ""))
    try:
        base = img.convert("RGBA")
        border = Image.open(path).convert("RGBA").resize(base.size, Image.LANCZOS)
        opacity = max(0, min(100, int(cfg.get("border_fx_opacity", 100) or 100))) / 100.0
        glow = max(0, min(100, int(cfg.get("border_fx_glow", 0) or 0))) / 100.0
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
        print(f"[BORDER FX ERR] {path} | {e}")
        return img


def apply_auto_enhance(img: Image.Image, cfg: dict | None) -> Image.Image:
    """Otomatik kontrast/doygunluk/parlaklık/keskinlik iyileştirmesi.
    Kırpma/border/metin katmanlarından ÖNCE, tüm canvas'a tek seferde uygulanır
    (parçalar ayrı ayrı iyileştirilirse her biri farklı histogram alıp
    Workshop parçaları arasında renk uyumsuzluğuna yol açardı)."""
    if not cfg or not bool(cfg.get("auto_enhance_enabled", False)):
        return img
    raw_intensity = cfg.get("auto_enhance_intensity", 50)
    if raw_intensity is None:  # "or 50" kullanılırsa gerçek 0 değeri de 50'ye döner
        raw_intensity = 50
    intensity = max(0, min(100, int(raw_intensity))) / 100.0
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
        print(f"[AUTO ENHANCE ERR] {e}")
        return img


_OVERLAY_FONT_CACHE: dict[int, "ImageFont.FreeTypeFont"] = {}
_OVERLAY_FONT_CANDIDATES = (
    r"C:\Windows\Fonts\seguisb.ttf",
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\arial.ttf",
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
    if font is None:
        font = ImageFont.load_default()
    _OVERLAY_FONT_CACHE[size] = font
    return font


_TEXT_OVERLAY_POSITIONS = (
    "Üst Sol", "Üst Orta", "Üst Sağ",
    "Alt Sol", "Alt Orta", "Alt Sağ",
    "Orta",
)


def apply_text_overlay(img: Image.Image, cfg: dict | None) -> Image.Image:
    """Görselin üstüne başlık/imza metni bindirir (border FX'ten sonra, en üstte).
    Uniform şablonlarda tüm canvas'a tek seferde uygulanır; Workshop parçaları
    yan yana dizilince metin de Border FX gibi bütün olarak birleşir."""
    if not cfg or not bool(cfg.get("text_overlay_enabled", False)):
        return img
    text = (cfg.get("text_overlay_text") or "").strip()
    if not text:
        return img
    try:
        base = img.convert("RGBA")
        layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)

        size_pct = max(1, min(30, int(cfg.get("text_overlay_size", 6) or 6)))
        font_size = max(10, int(base.height * size_pct / 100))
        font = _load_overlay_font(font_size)

        color = _parse_hex_color(cfg.get("text_overlay_color", "#FFFFFF"), (255, 255, 255))
        raw_opacity = cfg.get("text_overlay_opacity", 100)
        if raw_opacity is None:  # "or 100" kullanılırsa gerçek 0 değeri de 100'e döner
            raw_opacity = 100
        opacity = max(0, min(100, int(raw_opacity))) / 100.0
        alpha = int(255 * opacity)

        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        margin = max(8, int(base.width * 0.03))

        positions = {
            "Üst Sol": (margin, margin),
            "Üst Orta": ((base.width - tw) // 2, margin),
            "Üst Sağ": (base.width - tw - margin, margin),
            "Alt Sol": (margin, base.height - th - margin),
            "Alt Orta": ((base.width - tw) // 2, base.height - th - margin),
            "Alt Sağ": (base.width - tw - margin, base.height - th - margin),
            "Orta": ((base.width - tw) // 2, (base.height - th) // 2),
        }
        x, y = positions.get(cfg.get("text_overlay_position", "Alt Orta"), positions["Alt Orta"])
        x -= bbox[0]
        y -= bbox[1]

        # Okunabilirlik için ince koyu kontur
        shadow_alpha = int(alpha * 0.75)
        for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, -2), (-2, 2), (2, 2)):
            draw.text((x + ox, y + oy), text, font=font, fill=(0, 0, 0, shadow_alpha))
        draw.text((x, y), text, font=font, fill=color + (alpha,))

        return Image.alpha_composite(base, layer)
    except Exception as e:
        print(f"[TEXT OVERLAY ERR] {e}")
        return img


def _apply_effects_pipeline(img: Image.Image, cfg: dict | None) -> Image.Image:
    """Tüm canvas'a tek seferde: otomatik iyileştir -> border FX -> metin katmanı.
    Sıra önemli: iyileştirme kırpmadan önce (parçalar arası renk tutarlılığı),
    metin en üstte (border glow'un altında kalmasın)."""
    img = apply_auto_enhance(img, cfg)
    img = apply_border_fx(img, cfg)
    img = apply_text_overlay(img, cfg)
    return img


def _template_preview_canvas(img: Image.Image, template: dict) -> tuple[Image.Image, list[tuple[int, int, int, int]]]:
    """Şablonun kullanacağı canvas'ı ve parça kutularını üretir."""
    img = img.convert("RGBA")
    mode = template["mode"]

    if mode == "uniform":
        target_w = template["width"]
        target_h = template["height"]
        parts = template["parts"]
        # Sabit target_w x target_h canvas'a cover-crop (multi/single ile
        # tutarlı) — kaynağın kendi en-boy oranına göre değil.
        canvas = resize_cover(img, target_w, target_h)
        slice_w = target_w // parts
        boxes = [
            (i * slice_w, 0, (target_w if i == parts - 1 else (i + 1) * slice_w), target_h)
            for i in range(parts)
        ]
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


def render_template_preview(img: Image.Image, template: dict, border_cfg: dict | None = None) -> Image.Image:
    """Bölmeden önce kesim çizgilerini görselin üstüne çizer."""
    canvas, boxes = _template_preview_canvas(img, template)
    canvas = _apply_effects_pipeline(canvas, border_cfg)
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
        if i > 1:
            draw.line((x1, 0, x1, overlay.height), fill=line_color, width=3)
        label = f"#{i}"
        lx = x1 + 8
        ly = y1 + 8
        draw.rounded_rectangle((lx - 4, ly - 3, lx + 34, ly + 19),
                               radius=5, fill=label_fill)
        draw.text((lx, ly), label, fill=(255, 255, 255, 255))

    return overlay


def template_output_summary(img: Image.Image, template: dict) -> str:
    canvas, boxes = _template_preview_canvas(img, template)
    if not boxes:
        return ""
    first_w = boxes[0][2] - boxes[0][0]
    first_h = boxes[0][3] - boxes[0][1]
    mode = template.get("mode", "")
    patch = " · patch açık" if template.get("patch") else ""
    return f"{len(boxes)} parça · ilk çıktı {first_w}×{first_h}px · canvas {canvas.width}×{canvas.height}px{patch}"


# ==========================================================
#   ANİMASYONLU GIF SPLIT MOTORU
# ==========================================================

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
    Şeffaflık varsa korunur; aksi halde saydam/glow alanları siyaha dönerdi."""
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
        print(f"[PATCH SKIP] GIF dosyasında son byte patch uygulanmadı: {os.path.basename(outpath)}")


def split_gif_frames(path: str, outdir: str, template: dict, cfg: dict | None = None,
                     name_override: str | None = None):
    """
    Animasyonlu GIF’i frame-by-frame split eder.
    uniform, multi ve single modların tamamında animasyonlu GIF üretir.
    name_override verilirse çıktı adı kaynak dosya adı yerine bunu kullanır
    (toplu işlemde aynı isimli farklı kaynakların üstüne yazmasını önlemek için).
    """
    os.makedirs(outdir, exist_ok=True)
    created_files = []

    base = name_override or os.path.splitext(os.path.basename(path))[0]
    prefix = template.get("prefix", "parca")
    mode = template["mode"]

    frames, durations = _load_gif_frames(path)
    if not frames:
        return created_files

    # -------------------------------------------------------
    # MODE: UNIFORM
    # -------------------------------------------------------
    if mode == "uniform":
        target_w = template["width"]
        target_h = template["height"]
        parts = template["parts"]
        slice_w = target_w // parts

        # Sabit target_w x target_h canvas'a cover-crop — process_image
        # ve multi/single modlarıyla tutarlı (bkz. resize_cover).
        scaled = [_apply_effects_pipeline(resize_cover(f, target_w, target_h), cfg) for f in frames]

        for i in range(parts):
            x1 = i * slice_w
            x2 = target_w if i == parts - 1 else x1 + slice_w
            part_frames = [fr.crop((x1, 0, x2, target_h)) for fr in scaled]
            outpath = os.path.join(outdir, f"{prefix}_{base}_{i+1:02}.gif")
            _save_animated_gif(part_frames, durations, outpath, False)
            optimize_gif_file(outpath)
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
            optimize_gif_file(outpath)
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
        optimize_gif_file(outpath)
        created_files.append(outpath)

    print(f"[GIF SPLIT] {os.path.basename(path)} -> {len(created_files)} animasyonlu parca ({mode})")
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

        slice_w = target_w // parts

        for i in range(parts):
            x1 = i * slice_w
            x2 = target_w if i == parts - 1 else x1 + slice_w
            piece = img.crop((x1, 0, x2, target_h))
            fname = f"{prefix}_{base}_{i+1:02}.png"
            full = os.path.join(outdir, fname)
            piece.save(full)

            if template.get("patch"):
                patch_png_last_byte(full)

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

            fname = f"{prefix}_{base}_{index:02}.png"
            full = os.path.join(outdir, fname)
            piece.save(full)

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
        fname = f"{prefix}_{base}.png"
        full = os.path.join(outdir, fname)
        piece.save(full)
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


def split_multi_band(path: str, outdir: str, template: dict, band_count: int,
                     cfg: dict | None = None, name_override: str | None = None):
    """
    TEK yüksek çözünürlüklü kaynağı üstten alta doğru `band_count` adet
    BAĞIMSIZ target_h-yükseklik bandına ayırır, her bandı da uniform
    şablonun `parts` sayısı kadar eşit dikey dilime böler (Steam Community
    vitrinine sırayla yüklenince tek kesintisiz görsel gibi görünür).
    Kaynağın boyu istenen bant sayısını karşılamıyorsa sığdığı kadar TAM
    bant üretilir (kısmi/gerilmiş bant üretilmez) — çağıran taraf
    len(created) // parts ile kaç bant üretildiğini anlayabilir.
    """
    if template["mode"] != "uniform":
        raise ValueError("Çoklu bant sadece 'uniform' modundaki şablonlarda desteklenir")
    if band_count < 1:
        return []

    os.makedirs(outdir, exist_ok=True)
    base = name_override or os.path.splitext(os.path.basename(path))[0]
    prefix = template.get("prefix", "parca")
    target_w = template["width"]
    target_h = template["height"]
    parts = template["parts"]
    slice_w = target_w // parts

    original = Image.open(path).convert("RGBA")
    scale = target_w / original.width if original.width else 1.0
    scaled_h = max(1, int(original.height * scale))
    tall_canvas = _apply_effects_pipeline(
        original.resize((target_w, scaled_h), Image.LANCZOS), cfg)

    available_bands = scaled_h // target_h
    bands_to_make = min(band_count, available_bands)

    created = []
    for band in range(bands_to_make):
        y1 = band * target_h
        y2 = y1 + target_h
        for i in range(parts):
            x1 = i * slice_w
            x2 = target_w if i == parts - 1 else x1 + slice_w
            piece = tall_canvas.crop((x1, y1, x2, y2))
            idx = band * parts + i + 1
            fname = f"{prefix}_{base}_{idx:02}.png"
            full = os.path.join(outdir, fname)
            piece.save(full)

            if template.get("patch"):
                patch_png_last_byte(full)

            created.append(full)

    return created
