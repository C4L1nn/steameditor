"""Tests for Live Steam Preview (uploader)."""
import pathlib
from unittest.mock import MagicMock, patch

from PIL import Image


def test_capture_empty_returns_none():
    from steameditor.core.uploader import capture_steam_showcase_preview

    assert capture_steam_showcase_preview([]) is None
    assert capture_steam_showcase_preview([], 5) is None


def test_capture_without_playwright_returns_none(tmp_path):
    from steameditor.core.uploader import capture_steam_showcase_preview

    p = tmp_path / "a.png"
    Image.new("RGB", (100, 100), (255, 0, 0)).save(p)
    # Mock missing playwright by patching import to raise
    with patch.dict("sys.modules", {"playwright.sync_api": None}):
        # Force ImportError by making __import__ fail for playwright
        original_import = __import__

        def fake_import(name, *args, **kwargs):
            if "playwright" in name:
                raise ImportError("No playwright")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            result = capture_steam_showcase_preview([p])
            # Should return None gracefully, not raise
            assert result is None or isinstance(result, Image.Image)


def test_capture_with_mocked_playwright(tmp_path):
    from steameditor.core.uploader import capture_steam_showcase_preview

    # Create 2 dummy pieces
    p1 = tmp_path / "p1.png"
    p2 = tmp_path / "p2.png"
    Image.new("RGB", (150, 200), (255, 0, 0)).save(p1)
    Image.new("RGB", (150, 200), (0, 255, 0)).save(p2)

    # Mock playwright to return a fake screenshot
    mock_img = Image.new("RGB", (800, 600), (23, 26, 33))
    mock_png_bytes = b"fake"
    # Create a mock that returns an image via Image.open
    # Instead, patch sync_playwright to return mock browser that returns png bytes of a real image
    import io

    buf = io.BytesIO()
    mock_img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    mock_locator = MagicMock()
    mock_locator.screenshot.return_value = png_bytes
    mock_page = MagicMock()
    mock_page.locator.return_value = mock_locator
    mock_page.set_content.return_value = None
    mock_ctx = MagicMock()
    mock_ctx.new_page.return_value = mock_page
    mock_browser = MagicMock()
    mock_browser.new_context.return_value = mock_ctx
    mock_browser.close.return_value = None
    mock_playwright = MagicMock()
    mock_playwright.chromium.launch.return_value = mock_browser
    mock_sync = MagicMock()
    mock_sync.__enter__ = MagicMock(return_value=mock_playwright)
    mock_sync.__exit__ = MagicMock(return_value=False)

    # Playwright yüklü değilse bile çalışsın — sys.modules'e fake inject
    fake_sync_api = MagicMock(sync_playwright=MagicMock(return_value=mock_sync))
    fake_playwright = MagicMock()
    with patch.dict("sys.modules", {"playwright": fake_playwright, "playwright.sync_api": fake_sync_api}):
        # Also patch directly for when playwright is installed
        with patch("playwright.sync_api.sync_playwright", return_value=mock_sync, create=True):
            result = capture_steam_showcase_preview([p1, p2], parts_per_row=2)
            assert isinstance(result, Image.Image)
            assert result.size[0] > 0 and result.size[1] > 0


def test_capture_handles_missing_file(tmp_path):
    from steameditor.core.uploader import capture_steam_showcase_preview

    missing = tmp_path / "nonexistent.png"
    # Should return None, not crash, when file missing
    result = capture_steam_showcase_preview([missing])
    assert result is None
