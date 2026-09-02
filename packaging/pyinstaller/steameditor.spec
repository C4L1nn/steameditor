# -*- mode: python ; coding: utf-8 -*-

"""
PyInstaller spec for SplitForge - Cross-platform build configuration.

Usage:
    pyinstaller steameditor.spec          # Build for current platform
    pyinstaller --clean steameditor.spec  # Clean build
"""

import sys
import os
from pathlib import Path

# Project root
ROOT = Path(__file__).parent.parent.parent / "src"

# App metadata
APP_NAME = "SplitForge"
VERSION = "2.6.0"
APP_AUTHOR = "Aykut"
APP_DESCRIPTION = "Steam Showcase Studio - Professional Steam Workshop image splitter"

# Windows: prevent console window
WIN_NO_CONSOLE = True

# ─── Data Files ───
datas = [
    # Border templates
    (str(ROOT / "steameditor" / "resources" / "border_templates"), "resources/border_templates"),
    # Icons
    (str(ROOT / "steameditor" / "resources" / "app_icon.ico"), "resources"),
    (str(ROOT / "steameditor" / "resources" / "app_icon.png"), "resources"),
    # Color presets
    (str(ROOT / "steameditor" / "data" / "color_presets.json"), "data"),
]

# ─── Binaries ───
binaries = []

# Add platform-specific binaries
if sys.platform == "win32":
    # Windows: ffmpeg, gifsicle
    gif_bin = ROOT.parent / "GIF" / "bin"
    if gif_bin.exists():
        for exe in gif_bin.glob("*.exe"):
            binaries.append((str(exe), "bin"))
else:
    # Linux/macOS: assume ffmpeg/gifsicle in PATH or bundle
    pass

# ─── Hidden Imports ───
hiddenimports = [
    # Core
    "steameditor",
    "steameditor.core",
    "steameditor.core.models",
    "steameditor.core.processor",
    "steameditor.core.uploader",
    "steameditor.services",
    "steameditor.services.config_service",
    "steameditor.services.log_service",
    "steameditor.services.worker_pool",
    "steameditor.services.image_cache",
    "steameditor.ui",
    "steameditor.ui.app",
    "steameditor.ui.components",
    "steameditor.ui.design_system",
    "steameditor.ui.pages",
    "steameditor.ui.pages.settings_page",
    "steameditor.events",
    "steameditor.exceptions",
    "steameditor.config",
    "steameditor.config_legacy",
    "steameditor.plugins",
    "steameditor.updater",
    "steameditor.__main__",
    # PIL
    "PIL",
    "PIL._imaging",
    "PIL.Image",
    "PIL.ImageDraw",
    "PIL.ImageFont",
    "PIL.ImageFilter",
    "PIL.ImageEnhance",
    "PIL.ImageChops",
    "PIL.ImageOps",
    "PIL.ImageSequence",
    "PIL.ImageTk",
    "PIL.JpegImagePlugin",
    "PIL.PngImagePlugin",
    "PIL.GifImagePlugin",
    "PIL.WebPImagePlugin",
    # CustomTkinter
    "customtkinter",
    "tkinterdnd2",
    # Playwright
    "playwright",
    "playwright.sync_api",
    # Pydantic
    "pydantic",
    "pydantic_core",
    # Standard library
    "json",
    "pathlib",
    "threading",
    "subprocess",
    "webbrowser",
    "platform",
    "shutil",
    "tempfile",
    "uuid",
    "math",
    "time",
    "datetime",
    "logging",
    "logging.handlers",
    "queue",
    "concurrent.futures",
    "itertools",
    "functools",
    "collections",
    "dataclasses",
    "typing",
    "typing_extensions",
    "colorsys",
]

# Exclude unnecessary modules
excludes = [
    "matplotlib",
    "numpy",
    "scipy",
    "pandas",
    "torch",
    "tensorflow",
    "jupyter",
    "notebook",
    "IPython",
    "pytest",
    "sphinx",
    "setuptools",
    "pip",
    "wheel",
    "distutils",
    "html",
    "http",
    "xml",
    "email",
    "unittest",
    "doctest",
    "pdb",
    "profile",
    "pstats",
    "html.parser",
    "xml.etree",
    "xml.dom",
    "xml.sax",
    "html.entities",
    "html.parser",
]

# ─── Build ───
block_cipher = None

a = Analysis(
    ['steameditor/__main__.py'],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Platform-specific executable options
if sys.platform == "win32":
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=True,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=str(ROOT / "steameditor" / "resources" / "app_icon.ico"),
        version_file=str(ROOT.parent / "version.txt") if (ROOT.parent / "version.txt").exists() else None,
    )
elif sys.platform == "darwin":
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=True,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=str(ROOT / "steameditor" / "resources" / "app_icon.icns") if (ROOT / "steameditor" / "resources" / "app_icon.icns").exists() else None,
    )
    # Also create .app bundle
    app = BUNDLE(
        exe,
        name=f"{APP_NAME}.app",
        icon=str(ROOT / "steameditor" / "resources" / "app_icon.icns") if (ROOT / "steameditor" / "resources" / "app_icon.icns").exists() else None,
        bundle_identifier=f"com.{APP_AUTHOR.lower()}.{APP_NAME.lower()}",
        version=VERSION,
        info_plist={
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": APP_NAME,
            "CFBundleIdentifier": f"com.{APP_AUTHOR.lower()}.{APP_NAME.lower()}",
            "CFBundleVersion": VERSION,
            "CFBundleShortVersionString": VERSION,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "10.15",
        },
    )
else:  # Linux
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=True,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        icon=str(ROOT / "steameditor" / "resources" / "app_icon.png") if (ROOT / "steameditor" / "resources" / "app_icon.png").exists() else None,
    )