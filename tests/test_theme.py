"""Tests for Dark/Light theme toggle."""
import sys
from unittest.mock import patch


def test_light_colors_differ_from_dark():
    from steameditor.ui.design_system import _DARK_COLORS, _LIGHT_COLORS
    assert _DARK_COLORS.surface_0 != _LIGHT_COLORS.surface_0
    assert _DARK_COLORS.text_primary != _LIGHT_COLORS.text_primary
    # Light should be lighter
    assert _LIGHT_COLORS.surface_0.lower() != "#030303"
    assert _LIGHT_COLORS.text_primary.lower() == "#0f172a"


def test_toggle_theme_switches():
    # Mock ctk to avoid needing display
    with patch("customtkinter.set_appearance_mode"), patch("customtkinter.set_default_color_theme"):
        from steameditor.ui.design_system import get_theme, set_theme, toggle_theme, COLORS

        # Start from known state
        set_theme("dark")
        assert get_theme() == "dark"
        assert COLORS.surface_0 == "#030303"

        set_theme("light")
        assert get_theme() == "light"
        # Proxy should now return light values
        assert COLORS.surface_0.lower() == "#f8fafc"
        assert COLORS.text_primary.lower() == "#0f172a"

        toggle_theme()
        assert get_theme() == "dark"
        assert COLORS.surface_0 == "#030303"

        # Invalid falls back to dark
        set_theme("invalid")
        assert get_theme() == "dark"

        # Cleanup
        set_theme("dark")


def test_flat_config_theme_persistence():
    from steameditor.core.models import AppConfig
    from steameditor.services.flat_config import FlatConfig

    cfg = AppConfig()
    flat = FlatConfig(cfg)
    assert flat.get("theme", "dark") == "dark"
    flat["theme"] = "light"
    assert cfg.theme == "light"
    assert flat["theme"] == "light"
    flat["theme"] = "dark"
    assert cfg.theme == "dark"


def test_appconfig_theme_validation():
    from pydantic import ValidationError
    from steameditor.core.models import AppConfig

    cfg = AppConfig(theme="light")
    assert cfg.theme == "light"
    cfg2 = AppConfig(theme="system")
    assert cfg2.theme == "system"
    try:
        AppConfig(theme="invalid")  # type: ignore
        assert False, "should have raised"
    except ValidationError:
        pass
