import os

import pytest
from PIL import Image, ImageSequence

import gif


needs_ffmpeg = pytest.mark.skipif(
    gif.FFMPEG_MISSING, reason="ffmpeg bulunamadı (GİF/bin altında bundle değilse atlanır)")
needs_gifsicle = pytest.mark.skipif(
    gif.GIFSICLE_MISSING, reason="gifsicle bulunamadı")


# ── renk yardımcıları ─────────────────────────────────────

def test_h2r_r2h_roundtrip():
    assert gif._h2r("#ff8000") == (255, 128, 0)
    assert gif._r2h(255, 128, 0) == "#ff8000"


def test_lerp_midpoint():
    mid = gif.lerp("#000000", "#ffffff", 0.5)
    r, g, b = gif._h2r(mid)
    assert 120 <= r <= 135  # yuvarlama farkına tolerans


# ── efekt yardımcıları ────────────────────────────────────

def test_effect_border_colors_known_effect():
    border, inner = gif._effect_border_colors("neon")
    assert border == (124, 58, 237)
    assert inner == (34, 211, 238)


def test_effect_border_colors_unknown_falls_back_to_gray():
    border, inner = gif._effect_border_colors("does-not-exist")
    assert border == inner == (46, 46, 46)


def test_animation_frame_count_no_effect_is_single_frame():
    assert gif._animation_frame_count(3.0, 12, "none") == 1


def test_animation_frame_count_clamped_between_2_and_96():
    assert gif._animation_frame_count(0.01, 12, "neon") >= 2
    assert gif._animation_frame_count(1000, 24, "neon") <= 96


def test_paletteuse_filter_changes_with_lossy():
    assert "bayer_scale=5" in gif._paletteuse_filter(90)
    assert "bayer_scale=3" in gif._paletteuse_filter(50)
    assert "sierra2_4a" in gif._paletteuse_filter(10)


# ── border template mask/overlay (PIL, ffmpeg gerekmez) ──

def _real_template_name():
    templates = gif._list_border_templates()
    assert templates, "Border Templates klasöründe test için en az bir dosya olmalı"
    return templates[0]


def test_apply_border_template_none_is_noop():
    img = Image.new("RGB", (100, 100), (1, 2, 3))
    out = gif._apply_border_template(img, gif.BORDER_TEMPLATE_NONE, (255, 0, 0))
    assert list(out.getdata()) == list(img.getdata())


def test_apply_border_template_changes_pixels():
    img = Image.new("RGB", (200, 200), (10, 10, 10))
    out = gif._apply_border_template(img, _real_template_name(), (255, 0, 0), 0.5, 1.0)
    assert out.size == img.size
    assert list(out.getdata()) != list(img.getdata())


def test_apply_border_template_to_output_gif_applies_to_all_frames(tmp_path):
    """editor.py bug-fix regresyon testi: video kaynaklarından üretilen GIF/WebP
    çıktısına border template artık gerçekten bindiriliyor mu?
    (ffmpeg gerekmez — PIL ile küçük bir animasyonlu GIF üretip doğrudan test eder.)"""
    # Kareler kasıtlı olarak birbirinden farklı: aksi halde PIL'in GIF
    # optimize=True'su birebir aynı kareleri tek kareye birleştirir.
    from PIL import ImageDraw
    frames = []
    for i in range(3):
        f = Image.new("RGB", (60, 60), (10, 10, 10))
        ImageDraw.Draw(f).rectangle((5 + i * 10, 5, 20 + i * 10, 20), fill=(200, 200, 200))
        frames.append(f)
    out = tmp_path / "clip.gif"
    frames[0].save(out, save_all=True, append_images=frames[1:],
                   duration=[80, 80, 80], loop=0)
    before = list(Image.open(out).convert("RGB").getdata())

    gif._apply_border_template_to_output(
        str(out), "GIF", _real_template_name(), "neon", 60,
        colors=64, lossy=20, eff_dur=0.3, fps=10)

    after_img = Image.open(out)
    frame_count = sum(1 for _ in ImageSequence.Iterator(Image.open(out)))
    assert frame_count == 3
    after = list(after_img.convert("RGB").getdata())
    assert after != before


def test_apply_border_template_to_output_none_leaves_file_untouched(tmp_path):
    frames = [Image.new("RGB", (40, 40), (5, 5, 5)) for _ in range(2)]
    out = tmp_path / "clip.gif"
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=[80, 80], loop=0)
    before = out.read_bytes()

    gif._apply_border_template_to_output(str(out), "GIF", gif.BORDER_TEMPLATE_NONE, "neon", 60)

    assert out.read_bytes() == before


# ── gerçek ffmpeg/gifsicle ile uçtan uca (varsa) ──────────

@pytest.fixture(scope="module")
def synthetic_video(tmp_path_factory):
    if gif.FFMPEG_MISSING:
        pytest.skip("ffmpeg yok")
    tmp = tmp_path_factory.mktemp("video")
    path = tmp / "testsrc.mp4"
    gif.run([gif.FFMPEG, "-y", "-f", "lavfi",
             "-i", "testsrc=duration=1.2:size=320x240:rate=15",
             "-pix_fmt", "yuv420p", str(path)])
    assert path.exists()
    return str(path)


@needs_ffmpeg
def test_convert_video_to_gif_real(tmp_path, synthetic_video):
    out = tmp_path / "out.gif"
    ok, msg = gif._convert_video(
        synthetic_video, str(out), "GIF",
        fps=10, out_w=160, eff_dur=1.0, total_dur=1.2,
        lossy=25, colors=64, sharpen=False, smooth=False, effect="none")
    assert ok, msg
    assert out.exists() and out.stat().st_size > 0


@needs_ffmpeg
def test_convert_video_to_webp_real(tmp_path, synthetic_video):
    out = tmp_path / "out.webp"
    ok, msg = gif._convert_video(
        synthetic_video, str(out), "WebP",
        fps=10, out_w=160, eff_dur=1.0, total_dur=1.2,
        lossy=0, colors=256, sharpen=False, smooth=False, effect="none")
    assert ok, msg
    assert out.exists() and out.stat().st_size > 0


@needs_ffmpeg
def test_convert_video_applies_border_template_real(tmp_path, synthetic_video):
    """Gerçek ffmpeg ile: bulunan kritik bug'ın (Template video'da yok sayılıyordu)
    kalıcı regresyon testi."""
    out_plain = tmp_path / "plain.gif"
    out_tmpl = tmp_path / "with_template.gif"
    gif._convert_video(synthetic_video, str(out_plain), "GIF",
                       fps=10, out_w=160, eff_dur=0.8, total_dur=1.2,
                       lossy=25, colors=64, sharpen=False, smooth=False,
                       effect="none", border_template=gif.BORDER_TEMPLATE_NONE)
    gif._convert_video(synthetic_video, str(out_tmpl), "GIF",
                       fps=10, out_w=160, eff_dur=0.8, total_dur=1.2,
                       lossy=25, colors=64, sharpen=False, smooth=False,
                       effect="none", border_template=_real_template_name())

    frame_plain = next(iter(ImageSequence.Iterator(Image.open(out_plain)))).convert("RGB")
    frame_tmpl = next(iter(ImageSequence.Iterator(Image.open(out_tmpl)))).convert("RGB")
    assert list(frame_plain.getdata()) != list(frame_tmpl.getdata())


@needs_ffmpeg
def test_estimate_size_returns_positive_bytes(synthetic_video):
    est = gif._estimate_size(synthetic_video, fps=10, out_w=160, colors=64,
                             lossy=25, eff_dur=1.0, sharpen=False, smooth=False)
    assert est is not None and est > 0


def test_convert_image_png_to_webp(tmp_path):
    src = tmp_path / "src.png"
    Image.new("RGB", (300, 200), (80, 120, 200)).save(src)
    out = tmp_path / "out.webp"
    ok, msg = gif._convert_image(str(src), str(out), "WebP", 200, 2.0, 12, 20, 128,
                                 True, effect="none")
    assert ok, msg
    assert out.exists() and out.stat().st_size > 0


def test_convert_image_png_to_animated_gif_with_effect(tmp_path):
    src = tmp_path / "src.png"
    Image.new("RGB", (300, 200), (80, 120, 200)).save(src)
    out = tmp_path / "out.gif"
    ok, msg = gif._convert_image(str(src), str(out), "GIF", 200, 1.0, 12, 20, 64,
                                 True, effect="cyber_glitch", border=4, glow=50)
    assert ok, msg
    frame_count = sum(1 for _ in ImageSequence.Iterator(Image.open(out)))
    assert frame_count >= 2  # efektli statik görsel bile animasyonlu kare üretmeli
