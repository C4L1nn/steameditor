"""Tests for FlatConfig mapping and legacy migration."""
from steameditor.core.models import AppConfig
from steameditor.services.flat_config import FlatConfig


def test_flat_config_maps_top_fields():
    cfg = AppConfig(default_preset="Test", output_dir="/tmp")
    flat = FlatConfig(cfg)
    assert flat["default_preset"] == "Test"
    flat["default_preset"] = "New"
    assert cfg.default_preset == "New"
    assert flat.get("output_dir") == "/tmp"


def test_flat_config_maps_nested_effects():
    cfg = AppConfig()
    flat = FlatConfig(cfg)
    flat["border_fx_enabled"] = True
    flat["border_fx_color"] = "#FF0000"
    flat["border_fx_opacity"] = 77
    assert cfg.effects.border_fx.enabled is True
    assert cfg.effects.border_fx.color == "#FF0000"
    assert cfg.effects.border_fx.opacity == 77
    assert flat["border_fx_enabled"] is True
    assert flat.get("border_fx_color") == "#FF0000"


def test_flat_config_maps_output():
    cfg = AppConfig()
    flat = FlatConfig(cfg)
    flat["output_format"] = "jpg"
    flat["jpg_quality"] = 85
    flat["gif_lossy"] = 50
    flat["gif_colors"] = 128
    assert cfg.effects.output.format == "jpg"
    assert cfg.effects.output.jpg_quality == 85
    assert cfg.effects.output.gif_lossy == 50
    assert cfg.effects.output.gif_colors == 128


def test_flat_config_maps_steam():
    cfg = AppConfig()
    flat = FlatConfig(cfg)
    flat["steam_api_key"] = "key123"
    flat["steam_community_upload_url"] = "https://example.com"
    flat["steam_community_auto_submit"] = True
    assert cfg.steam.api_key == "key123"
    assert cfg.steam.community_url == "https://example.com"
    assert cfg.steam.auto_submit is True


def test_flat_config_extras():
    cfg = AppConfig()
    flat = FlatConfig(cfg)
    flat["unknown_key"] = "val"
    assert flat["unknown_key"] == "val"
    assert "unknown_key" in flat
    del flat["unknown_key"]
    assert "unknown_key" not in flat


def test_flat_config_legacy_migration_mapping():
    # Simulate legacy dict -> AppConfig via ConfigService helper
    from steameditor.services.config_service import ConfigService
    import tempfile, pathlib, json

    tmp = pathlib.Path(tempfile.mkdtemp())
    legacy = {
        "default_preset": "Atölye Vitrini 5-Parça (150×1250)",
        "output_dir": "C:/out",
        "border_fx_enabled": True,
        "border_fx_color": "#00FF00",
        "output_format": "jpg",
        "jpg_quality": 90,
        "steam_api_key": "abc",
        "steam_community_auto_submit": True,
        "auto_enhance_enabled": True,
        "auto_enhance_intensity": 60,
    }
    # Use private helper
    svc = object.__new__(ConfigService)
    mapped = svc._legacy_to_appconfig(legacy)
    assert mapped["default_preset"] == "Atölye Vitrini 5-Parça (150×1250)"
    assert mapped["effects"]["border_fx"]["enabled"] is True
    assert mapped["effects"]["border_fx"]["color"] == "#00FF00"
    assert mapped["effects"]["output"]["format"] == "jpg"
    assert mapped["steam"]["api_key"] == "abc"
    assert mapped["steam"]["auto_submit"] is True
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
