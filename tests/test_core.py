import os

import pytest
from PIL import Image, ImageSequence

import core


# ── resize_cover ──────────────────────────────────────────

def test_resize_cover_output_size_matches_target():
    img = Image.new("RGB", (800, 400), (10, 20, 30))
    out = core.resize_cover(img, 300, 300)
    assert out.size == (300, 300)


def test_resize_cover_preserves_aspect_no_distortion():
    # Kare hedefe dikdörtgen kaynak: kırpma olmalı, gerilme olmamalı.
    img = Image.new("RGB", (1000, 200), (255, 0, 0))
    out = core.resize_cover(img, 100, 100)
    assert out.size == (100, 100)


# ── _parse_hex_color ──────────────────────────────────────

@pytest.mark.parametrize("value,expected", [
    ("#FF0000", (255, 0, 0)),
    ("00FF00", (0, 255, 0)),
    ("#00f", (0, 0, 255)),
    ("f00", (255, 0, 0)),
])
def test_parse_hex_color_valid(value, expected):
    assert core._parse_hex_color(value) == expected


@pytest.mark.parametrize("value", ["", "nope", "#12", "#1234567"])
def test_parse_hex_color_invalid_falls_back(value):
    fallback = (139, 92, 246)
    assert core._parse_hex_color(value, fallback) == fallback


# ── _border_cfg_enabled / apply_border_fx ────────────────

def _real_template_name():
    templates = core.list_border_templates()
    assert templates, "Border Templates klasöründe test için en az bir dosya olmalı"
    return templates[0]


def test_border_cfg_enabled_false_when_no_cfg():
    assert core._border_cfg_enabled(None) is False


def test_border_cfg_enabled_false_when_disabled():
    cfg = {"border_fx_enabled": False, "border_fx_template": _real_template_name()}
    assert core._border_cfg_enabled(cfg) is False


def test_border_cfg_enabled_false_when_template_missing():
    cfg = {"border_fx_enabled": True, "border_fx_template": "nope_does_not_exist.png"}
    assert core._border_cfg_enabled(cfg) is False


def test_border_cfg_enabled_true_when_valid():
    cfg = {"border_fx_enabled": True, "border_fx_template": _real_template_name()}
    assert core._border_cfg_enabled(cfg) is True


def test_apply_border_fx_noop_when_disabled():
    img = Image.new("RGBA", (100, 100), (10, 10, 10, 255))
    out = core.apply_border_fx(img, {"border_fx_enabled": False})
    assert out.size == img.size


def test_apply_border_fx_changes_pixels_when_enabled():
    img = Image.new("RGBA", (200, 200), (10, 10, 10, 255))
    cfg = {
        "border_fx_enabled": True,
        "border_fx_template": _real_template_name(),
        "border_fx_color": "#FF0000",
        "border_fx_opacity": 100,
        "border_fx_glow": 50,
    }
    out = core.apply_border_fx(img, cfg)
    assert out.size == img.size
    assert list(out.getdata()) != list(img.convert("RGBA").getdata())


# ── apply_auto_enhance ─────────────────────────────────────

def test_apply_auto_enhance_noop_when_disabled():
    img = Image.new("RGB", (100, 100), (80, 90, 100))
    out = core.apply_auto_enhance(img, {"auto_enhance_enabled": False})
    assert list(out.convert("RGB").getdata()) == list(img.getdata())


def test_apply_auto_enhance_noop_when_intensity_zero():
    img = Image.new("RGB", (100, 100), (80, 90, 100))
    out = core.apply_auto_enhance(img, {"auto_enhance_enabled": True, "auto_enhance_intensity": 0})
    assert list(out.convert("RGB").getdata()) == list(img.getdata())


def test_apply_auto_enhance_changes_pixels_when_enabled():
    img = Image.new("RGB", (100, 100), (80, 90, 100))
    out = core.apply_auto_enhance(img, {"auto_enhance_enabled": True, "auto_enhance_intensity": 80})
    assert list(out.convert("RGB").getdata()) != list(img.getdata())


def test_apply_auto_enhance_preserves_alpha_channel():
    img = Image.new("RGBA", (50, 50), (80, 90, 100, 128))
    out = core.apply_auto_enhance(img, {"auto_enhance_enabled": True, "auto_enhance_intensity": 90})
    assert out.getchannel("A").getextrema() == (128, 128)


# ── apply_text_overlay ─────────────────────────────────────

def test_apply_text_overlay_noop_when_disabled():
    img = Image.new("RGB", (300, 200), (10, 10, 10))
    out = core.apply_text_overlay(img, {"text_overlay_enabled": False, "text_overlay_text": "HI"})
    assert list(out.convert("RGB").getdata()) == list(img.getdata())


def test_apply_text_overlay_noop_when_text_empty():
    img = Image.new("RGB", (300, 200), (10, 10, 10))
    out = core.apply_text_overlay(img, {"text_overlay_enabled": True, "text_overlay_text": "   "})
    assert list(out.convert("RGB").getdata()) == list(img.getdata())


def test_apply_text_overlay_zero_opacity_is_invisible():
    """Regresyon: 'cfg.get(key, default) or default' deseni gerçek 0 değerini
    de varsayılana çevirirdi (opacity=0 -> 100 gibi). 0 gerçekten görünmez olmalı."""
    img = Image.new("RGB", (300, 200), (10, 10, 10))
    out = core.apply_text_overlay(img, {
        "text_overlay_enabled": True, "text_overlay_text": "GHOST",
        "text_overlay_color": "#FFFFFF", "text_overlay_size": 10,
        "text_overlay_position": "Orta", "text_overlay_opacity": 0,
    })
    assert list(out.convert("RGB").getdata()) == list(img.getdata())


def test_apply_text_overlay_draws_text_at_requested_position():
    img = Image.new("RGB", (400, 300), (10, 10, 10))
    out = core.apply_text_overlay(img, {
        "text_overlay_enabled": True, "text_overlay_text": "STEAM MOD",
        "text_overlay_color": "#FFFFFF", "text_overlay_size": 10,
        "text_overlay_position": "Alt Orta", "text_overlay_opacity": 100,
    })
    assert out.size == img.size
    bottom = out.crop((0, 250, 400, 300)).convert("RGB")
    assert any(p[0] > 150 for p in bottom.getdata()), "metin alt bölgede görünmüyor"
    top = out.crop((0, 0, 400, 50)).convert("RGB")
    assert all(p == (10, 10, 10) for p in top.getdata()), "metin yanlış konumda (üstte) görünüyor"


# ── _apply_effects_pipeline / uniform parça bütünlüğü ─────

def test_effects_pipeline_text_reads_coherently_across_uniform_parts(tmp_path):
    """Workshop 5-parça modunda metin/border tüm canvas'a TEK seferde
    uygulanmalı; aksi halde her parça kendi histogramına göre farklı
    işlenir ve Steam'de yan yana dizilince renk/metin uyumsuz görünür."""
    src = tmp_path / "src.png"
    Image.new("RGB", (1508, 1000), (40, 60, 90)).save(src)
    cfg = {
        "text_overlay_enabled": True, "text_overlay_text": "COHERENT TEXT",
        "text_overlay_color": "#FACC15", "text_overlay_size": 8,
        "text_overlay_position": "Alt Orta", "text_overlay_opacity": 100,
    }
    template = {"name": "t", "mode": "uniform", "width": 750, "height": 1250, "parts": 5,
                "patch": False, "prefix": "t"}
    created = sorted(core.process_image(str(src), str(tmp_path), template, cfg))
    assert len(created) == 5

    parts = [Image.open(p).convert("RGB") for p in created]
    stitched = Image.new("RGB", (sum(p.width for p in parts), parts[0].height))
    x = 0
    for p in parts:
        stitched.paste(p, (x, 0))
        x += p.width

    bottom = stitched.crop((0, stitched.height - 60, stitched.width, stitched.height))
    bright_pixels = sum(1 for p in bottom.getdata() if p[0] > 150 and p[1] > 150)
    # Metin birleştirilmiş görüntüde makul sayıda parlak piksel üretmeli
    # (tek bir parçaya sıkışıp kaybolmamış, gerçekten okunur genişlikte).
    assert bright_pixels > 200, f"birlestirilmis metin beklenenden az goruluyor ({bright_pixels} piksel)"


# ── _template_preview_canvas ──────────────────────────────

def test_uniform_boxes_cover_full_width_when_divisible():
    img = Image.new("RGB", (1000, 800))
    template = {"mode": "uniform", "width": 750, "height": 1250, "parts": 5}
    canvas, boxes = core._template_preview_canvas(img, template)
    assert len(boxes) == 5
    assert boxes[0][0] == 0
    assert boxes[-1][2] == 750
    # Ardışık kutular boşluksuz/çakışmasız bitişik olmalı
    for i in range(len(boxes) - 1):
        assert boxes[i][2] == boxes[i + 1][0]


def test_uniform_last_box_absorbs_remainder_pixels():
    # 754 // 5 = 150 kalan 4 -> son parça 150+4=154 olmalı, piksel kaybı olmamalı
    img = Image.new("RGB", (1000, 800))
    template = {"mode": "uniform", "width": 754, "height": 1250, "parts": 5}
    _, boxes = core._template_preview_canvas(img, template)
    widths = [b[2] - b[0] for b in boxes]
    assert widths == [150, 150, 150, 150, 154]
    assert sum(widths) == 754


def test_uniform_canvas_height_matches_template_not_source_aspect_ratio():
    """Regresyon: önizleme canvas'ı da (dolayısıyla 'ilk çıktı WxH' durum
    metni) kaynağın oranına göre değil, şablonun kendi height'ına göre
    üretilmeli — bkz. test_process_image_uniform_uses_template_height_..."""
    wide_img = Image.new("RGB", (5120, 2880))  # 16:9, hedeften çok farklı oran
    template = {"mode": "uniform", "width": 750, "height": 1250, "parts": 5}
    canvas, boxes = core._template_preview_canvas(wide_img, template)
    assert canvas.size == (750, 1250)
    assert boxes[0] == (0, 0, 150, 1250)


def test_multi_boxes_match_part_definitions():
    img = Image.new("RGB", (1000, 800))
    template = {"mode": "multi", "parts": [
        {"width": 506, "height": 800},
        {"width": 100, "height": 800},
    ]}
    canvas, boxes = core._template_preview_canvas(img, template)
    assert canvas.size == (606, 800)
    assert boxes == [(0, 0, 506, 800), (506, 0, 606, 800)]


def test_single_box_is_full_canvas():
    img = Image.new("RGB", (1000, 800))
    template = {"mode": "single", "width": 650, "height": 850}
    canvas, boxes = core._template_preview_canvas(img, template)
    assert canvas.size == (650, 850)
    assert boxes == [(0, 0, 650, 850)]


def test_template_output_summary_mentions_part_count_and_patch():
    img = Image.new("RGB", (1000, 800))
    template = {"mode": "uniform", "width": 750, "height": 1250, "parts": 5, "patch": True}
    summary = core.template_output_summary(img, template)
    assert "5 parça" in summary
    assert "patch açık" in summary


# ── _save_animated_gif ────────────────────────────────────

def _make_gif_frames(transparent):
    from PIL import ImageDraw
    frames = []
    for i in range(3):
        f = Image.new("RGBA", (40, 40), (0, 0, 0, 0) if transparent else (255, 255, 255, 255))
        d = ImageDraw.Draw(f)
        d.rectangle((5 + i * 5, 5, 25 + i * 5, 25), fill=(0, 200, 0, 255))
        frames.append(f)
    return frames


def test_save_animated_gif_preserves_transparency(tmp_path):
    frames = _make_gif_frames(transparent=True)
    out = tmp_path / "trans.gif"
    core._save_animated_gif(frames, [100, 100, 100], str(out))

    im = Image.open(out)
    frame_count = sum(1 for _ in ImageSequence.Iterator(Image.open(out)))
    assert frame_count == 3

    im.seek(0)
    rgba = im.convert("RGBA")
    assert rgba.getpixel((0, 0))[3] == 0        # köşe hâlâ şeffaf
    assert rgba.getpixel((15, 15))[3] == 255    # yeşil kare opak


def test_save_animated_gif_opaque_frames_no_crash(tmp_path):
    frames = _make_gif_frames(transparent=False)
    out = tmp_path / "opaque.gif"
    core._save_animated_gif(frames, [100, 100, 100], str(out))
    frame_count = sum(1 for _ in ImageSequence.Iterator(Image.open(out)))
    assert frame_count == 3


# ── process_image / process_folder ────────────────────────

def test_process_image_uniform_remainder_pixels(tmp_path):
    src = tmp_path / "src.png"
    Image.new("RGB", (1508, 1000), (200, 100, 50)).save(src)
    template = {"name": "t", "mode": "uniform", "width": 754, "height": 1250, "parts": 5,
                "patch": False, "prefix": "t"}
    created = core.process_image(str(src), str(tmp_path), template, None)
    widths = [Image.open(p).size[0] for p in created]
    assert widths == [150, 150, 150, 150, 154]
    assert sum(widths) == 754


def test_process_image_uniform_uses_template_height_not_source_aspect_ratio(tmp_path):
    """Regresyon: uniform mod kaynağın KENDİ en-boy oranına göre 'dinamik'
    yükseklik hesaplıyordu, şablonun kendi height alanını yok sayıyordu.
    Geniş (16:9) bir kaynakta bu, her parçayı 150x421 gibi sıkışık bir
    şeride çeviriyor, içeriğin çoğu boş/karanlık kenar parçalara düşüyordu.
    Şablonun height'ı (1250) kaynağın oranından BAĞIMSIZ olarak korunmalı
    (resize_cover ile cover-crop, multi/single modlarıyla tutarlı)."""
    src = tmp_path / "wide_16_9.png"
    Image.new("RGB", (5120, 2880), (200, 100, 50)).save(src)
    template = {"name": "t", "mode": "uniform", "width": 750, "height": 1250, "parts": 5,
                "patch": False, "prefix": "t"}
    created = core.process_image(str(src), str(tmp_path), template, None)
    sizes = [Image.open(p).size for p in created]
    assert sizes == [(150, 1250)] * 5


def test_process_image_name_override_used_for_output_filename(tmp_path):
    src = tmp_path / "weird_source_name.png"
    Image.new("RGB", (300, 200), (1, 2, 3)).save(src)
    template = {"name": "t", "mode": "single", "width": 100, "height": 100, "prefix": "shot"}
    created = core.process_image(str(src), str(tmp_path), template, None,
                                 name_override="override_stem")
    assert len(created) == 1
    assert os.path.basename(created[0]) == "shot_override_stem.png"


def test_process_image_name_override_prevents_collision_between_sources(tmp_path):
    """İki farklı kaynak dosya aynı ada (stem) sahipse, name_override
    olmadan ikincisi birincinin çıktısını sessizce ezerdi."""
    src_a = tmp_path / "a" / "photo.png"
    src_b = tmp_path / "b" / "photo.png"
    src_a.parent.mkdir(); src_b.parent.mkdir()
    Image.new("RGB", (100, 100), (255, 0, 0)).save(src_a)
    Image.new("RGB", (100, 100), (0, 255, 0)).save(src_b)
    template = {"name": "t", "mode": "single", "width": 50, "height": 50, "prefix": "shot"}

    created_a = core.process_image(str(src_a), str(tmp_path), template, None)
    created_b = core.process_image(str(src_b), str(tmp_path), template, None,
                                   name_override="photo_2")

    assert created_a[0] != created_b[0]
    assert os.path.exists(created_a[0]) and os.path.exists(created_b[0])
    assert Image.open(created_a[0]).convert("RGB").getpixel((0, 0)) == (255, 0, 0)
    assert Image.open(created_b[0]).convert("RGB").getpixel((0, 0)) == (0, 255, 0)


def test_process_image_uniform_patch_sets_last_byte(tmp_path):
    src = tmp_path / "src.png"
    Image.new("RGB", (750, 500), (0, 0, 0)).save(src)
    template = {"name": "t", "mode": "uniform", "width": 750, "height": 1250, "parts": 5,
                "patch": True, "prefix": "t"}
    created = core.process_image(str(src), str(tmp_path), template, None)
    assert len(created) == 5
    for path in created:
        with open(path, "rb") as f:
            data = f.read()
        assert data[-1] == 0x21


# ── split_multi_band ───────────────────────────────────────

def _striped_source(tmp_path, width=100, band_h=200, colors=((255, 0, 0), (0, 0, 255)), leftover=50):
    """Her `band_h` satırlık şeridi farklı renkte olan bir test kaynağı üretir,
    sonuna da bir sonraki tam bandı doldurmayan `leftover` piksellik bir
    kalan ekler (banda dahil edilmemesi gerektiğini doğrulamak için)."""
    total_h = band_h * len(colors) + leftover
    img = Image.new("RGB", (width, total_h))
    for i, color in enumerate(colors):
        for y in range(i * band_h, (i + 1) * band_h):
            for x in range(width):
                img.putpixel((x, y), color)
    src = tmp_path / "striped.png"
    img.save(src)
    return str(src)


def test_split_multi_band_produces_requested_bands_when_source_fits(tmp_path):
    src = _striped_source(tmp_path)
    template = {"name": "t", "mode": "uniform", "width": 100, "height": 200, "parts": 2,
                "patch": False, "prefix": "t"}
    created = core.split_multi_band(src, str(tmp_path), template, 2, None)
    assert len(created) == 4  # 2 bant x 2 parça


def test_split_multi_band_caps_at_available_source_height(tmp_path):
    """3 bant istense bile kaynak sadece 2 tam banda yetiyorsa 2 bant üretilmeli,
    gerilmiş/kısmi bir 3. bant ASLA üretilmemeli."""
    src = _striped_source(tmp_path)
    template = {"name": "t", "mode": "uniform", "width": 100, "height": 200, "parts": 2,
                "patch": False, "prefix": "t"}
    created = core.split_multi_band(src, str(tmp_path), template, 3, None)
    assert len(created) == 4  # istenen 3 değil, sığan 2 bant


def test_split_multi_band_bands_contain_distinct_source_regions(tmp_path):
    """2. bant 1. bandın kopyası olmamalı — gerçekten farklı bir dikey
    aralıktan (kaynağın 200-400. satırları) kesilmeli."""
    src = _striped_source(tmp_path)
    template = {"name": "t", "mode": "uniform", "width": 100, "height": 200, "parts": 2,
                "patch": False, "prefix": "t"}
    created = sorted(core.split_multi_band(src, str(tmp_path), template, 2, None))
    band1_part1 = Image.open(created[0]).convert("RGB").getpixel((5, 5))
    band2_part1 = Image.open(created[2]).convert("RGB").getpixel((5, 5))
    assert band1_part1 == (255, 0, 0)
    assert band2_part1 == (0, 0, 255)
    assert band1_part1 != band2_part1


def test_split_multi_band_rejects_non_uniform_template(tmp_path):
    src = _striped_source(tmp_path)
    template = {"name": "t", "mode": "single", "width": 100, "height": 100, "prefix": "t"}
    with pytest.raises(ValueError):
        core.split_multi_band(src, str(tmp_path), template, 2, None)


def test_split_multi_band_zero_bands_requested_returns_empty(tmp_path):
    src = _striped_source(tmp_path)
    template = {"name": "t", "mode": "uniform", "width": 100, "height": 200, "parts": 2,
                "patch": False, "prefix": "t"}
    assert core.split_multi_band(src, str(tmp_path), template, 0, None) == []


def test_process_image_multi_creates_expected_sizes(tmp_path):
    src = tmp_path / "src.png"
    Image.new("RGB", (400, 300), (1, 2, 3)).save(src)
    template = {"name": "t", "mode": "multi", "prefix": "art",
                "parts": [{"width": 506, "height": 800}, {"width": 100, "height": 800}]}
    created = core.process_image(str(src), str(tmp_path), template, None)
    assert len(created) == 2
    sizes = sorted(Image.open(p).size for p in created)
    assert sizes == [(100, 800), (506, 800)]


def test_process_image_single_creates_expected_size(tmp_path):
    src = tmp_path / "src.png"
    Image.new("RGB", (1200, 900), (5, 5, 5)).save(src)
    template = {"name": "t", "mode": "single", "width": 650, "height": 850, "prefix": "shot"}
    created = core.process_image(str(src), str(tmp_path), template, None)
    assert len(created) == 1
    assert Image.open(created[0]).size == (650, 850)


def test_process_folder_processes_all_images(tmp_path):
    src_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    src_dir.mkdir()
    for i in range(3):
        Image.new("RGB", (300, 300), (i, i, i)).save(src_dir / f"img_{i}.png")
    template = {"name": "t", "mode": "single", "width": 100, "height": 100, "prefix": "shot"}
    created = core.process_folder(str(src_dir), str(out_dir), template, None)
    assert len(created) == 3


def test_split_gif_frames_uniform_produces_animated_parts(tmp_path):
    frames = _make_gif_frames(transparent=False)
    src = tmp_path / "src.gif"
    frames[0].convert("RGB").save(
        src, save_all=True, append_images=[f.convert("RGB") for f in frames[1:]],
        duration=[80, 80, 80], loop=0)

    template = {"name": "t", "mode": "uniform", "width": 40, "height": 40, "parts": 2,
                "patch": False, "prefix": "t"}
    created = core.split_gif_frames(str(src), str(tmp_path), template, None)
    assert len(created) == 2
    for path in created:
        frame_count = sum(1 for _ in ImageSequence.Iterator(Image.open(path)))
        assert frame_count == 3


def test_split_gif_frames_name_override_used_for_output_filename(tmp_path):
    frames = _make_gif_frames(transparent=False)
    src = tmp_path / "any_name.gif"
    frames[0].convert("RGB").save(
        src, save_all=True, append_images=[f.convert("RGB") for f in frames[1:]],
        duration=[80, 80, 80], loop=0)
    template = {"name": "t", "mode": "single", "width": 40, "height": 40, "prefix": "shot"}
    created = core.split_gif_frames(str(src), str(tmp_path), template, None,
                                    name_override="renamed_stem")
    assert len(created) == 1
    assert os.path.basename(created[0]) == "shot_renamed_stem.gif"


# ── patch helpers ─────────────────────────────────────────

def test_patch_png_last_byte_changes_last_byte(tmp_path):
    p = tmp_path / "a.png"
    p.write_bytes(b"\x00\x01\x02\x03")
    core.patch_png_last_byte(str(p), 0x21)
    assert p.read_bytes()[-1] == 0x21


def test_patch_gif_trailing_byte_changes_when_different(tmp_path):
    p = tmp_path / "a.gif"
    p.write_bytes(b"\x00\x01\x02\x03")
    core.patch_gif_trailing_byte(str(p), 0x21)
    assert p.read_bytes()[-1] == 0x21


def test_patch_gif_trailing_byte_noop_when_already_matches(tmp_path):
    p = tmp_path / "a.gif"
    p.write_bytes(b"\x00\x01\x02\x21")
    core.patch_gif_trailing_byte(str(p), 0x21)
    assert p.read_bytes() == b"\x00\x01\x02\x21"
