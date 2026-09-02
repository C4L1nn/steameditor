"""Tests for Smart AutoCrop — border/subject/both."""
import sys

from PIL import Image, ImageDraw

import steameditor.core.processor as proc


def _solid_with_inner_rect():
    # 200x200 black border, inner 100x100 red
    img = Image.new("RGB", (200, 200), (0, 0, 0))
    ImageDraw.Draw(img).rectangle((50, 50, 149, 149), fill=(200, 50, 50))
    return img


def test_subject_bbox_fallback_without_rembg():
    # rembg not installed in CI → should return None, not crash
    img = Image.new("RGB", (100, 100), (0, 0, 0))
    # Ensure _subject_bbox doesn't raise when rembg missing
    # If rembg is installed, it may return a bbox; either way should not raise
    try:
        bbox = proc._subject_bbox(img)
        # If rembg not present, bbox is None; if present, bbox is tuple or None
        assert bbox is None or isinstance(bbox, tuple)
    except ImportError:
        # Should not propagate
        assert False, "_subject_bbox should handle missing rembg gracefully"


def test_autocrop_bbox_smart_border_mode():
    img = _solid_with_inner_rect()
    bbox = proc._autocrop_bbox_smart(img, {"autocrop_mode": "border"})
    # border mode should find inner rect exactly
    assert bbox == (50, 50, 150, 150)


def test_autocrop_bbox_smart_subject_fallback_to_border():
    img = _solid_with_inner_rect()
    # subject mode without rembg should fallback to border
    bbox = proc._autocrop_bbox_smart(img, {"autocrop_mode": "subject"})
    assert bbox == (50, 50, 150, 150)


def test_autocrop_bbox_smart_both_union():
    img = _solid_with_inner_rect()
    # Both mode: if subject is None, should return border
    bbox = proc._autocrop_bbox_smart(img, {"autocrop_mode": "both"})
    assert bbox == (50, 50, 150, 150)


def test_autocrop_borders_respects_mode():
    img = _solid_with_inner_rect()
    # Enabled + border mode
    out = proc.autocrop_borders(img, {"autocrop_enabled": True, "autocrop_mode": "border"})
    assert out.size == (100, 100)
    # Disabled should be no-op
    out2 = proc.autocrop_borders(img, {"autocrop_enabled": False, "autocrop_mode": "border"})
    assert out2.size == (200, 200)
    # Both mode also should crop to at least border
    out3 = proc.autocrop_borders(img, {"autocrop_enabled": True, "autocrop_mode": "both"})
    assert out3.size == (100, 100)


def test_autocrop_borders_unknown_mode_fallback():
    img = _solid_with_inner_rect()
    out = proc.autocrop_borders(img, {"autocrop_enabled": True, "autocrop_mode": "unknown_mode"})
    # Should fallback to border or both union, still crop
    assert out.size == (100, 100)


def test_flat_config_autocrop_mode():
    from steameditor.core.models import AppConfig
    from steameditor.services.flat_config import FlatConfig

    cfg = AppConfig()
    flat = FlatConfig(cfg)
    assert flat.get("autocrop_mode", "border") == "border"
    flat["autocrop_mode"] = "subject"
    assert cfg.effects.autocrop_mode == "subject"
    assert flat["autocrop_mode"] == "subject"
    flat["autocrop_mode"] = "both"
    assert cfg.effects.autocrop_mode == "both"


def test_appconfig_autocrop_mode_validation():
    from pydantic import ValidationError
    from steameditor.core.models import AppConfig

    cfg = AppConfig(effects={"autocrop_mode": "subject"})
    assert cfg.effects.autocrop_mode == "subject"
    try:
        AppConfig(effects={"autocrop_mode": "invalid"})  # type: ignore
        assert False, "should have raised"
    except ValidationError:
        pass
