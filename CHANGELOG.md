# Changelog

All notable changes to SplitForge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.0.0] - 2024-01-15

### 🎉 Major Release - Complete Rewrite

### ✨ Added
- **New Modular Architecture**: Complete restructure with `src/steameditor/` package
- **Pydantic Models**: Type-safe configuration (Template, EffectConfig, Profile, Project)
- **Service Layer**: ConfigService, WorkerPool, ImageCache, LogService
- **Event Bus**: Decoupled communication between components
- **Custom Exception Hierarchy**: SteamEditorError with user-friendly messages
- **Professional Design System**: Carbon × Steam Orange theme with animations

### 🎨 UI/UX
- **Interactive Preview**: Drag/resize grid, real-time band management
- **Effects Panel**: Auto-crop, Auto-enhance, Border FX (10 templates), Text Overlay (draggable)
- **Projects & Profiles**: Save/restore complete workflows
- **Keyboard Shortcuts**: Ctrl+O, Ctrl+Enter, Esc, drag/drop
- **Accessibility**: Focus management, high contrast, screen reader support

### 🖼️ Processing
- **Uniform Slice**: Remainder pixels distributed to FIRST parts (Steam-compatible)
- **Multi-Band**: Horizontal bands for tall images (1-20 bands)
- **Manual Crop**: Interactive grid with pixel-perfect positioning
- **GIF Support**: Frame-by-frame split with gifsicle optimization
- **Batch Processing**: Folder → queue → parallel processing
- **Format Support**: PNG, JPG, WEBP, GIF input/output
- **Steam Patch**: Automatic PNG last-byte `0x21` patch

### 🎮 Steam Integration
- **Console Snippets**: 3 verified snippets (Workshop, Artwork, Screenshot)
- **Auto-Upload**: Background upload with progress
- **Auto-Submit**: Optional form submission
- **Custom Upload URL**: Per-project Steam URL
- **PublishedFileID**: Per-project update support

### 🎬 GIF Maker (Standalone)
- **Video → GIF/WebP**: ffmpeg + gifsicle pipeline
- **12 Effect Presets**: Neon, VHS, Cinema, Glitch, etc.
- **Border Templates**: Applied to all frames
- **Size Estimation**: Pre-compression size prediction

### 🛠️ Developer Experience
- **117 Tests**: 100% passing (core, config, gif_engine)
- **Type Safety**: Pyright strict mode on core modules
- **Linting**: Ruff + pre-commit hooks
- **CI/CD**: GitHub Actions (lint, test, build, installer, release)
- **Documentation**: User guide, developer docs, API reference

### 📦 Distribution
- **PyInstaller Spec**: Single-file executable + resources
- **NSIS Installer**: Professional installer with shortcuts
- **Auto-Updater**: GitHub Releases check with silent download
- **Resources**: Border templates, icons bundled

---

## [1.5.0] - 2023-11-20

### Added
- Multi-band support for tall images
- Interactive grid preview with drag/resize
- Border FX with glow effect
- Text overlay with drag positioning
- Auto-enhance (contrast/saturation/sharpness)

### Fixed
- PNG patch now applied after gifsicle optimization
- GIF frame disposal method fixed (disposal=2)
- Multi-band grid capping at source height

---

## [1.4.0] - 2023-09-10

### Added
- Steam Community upload automation
- Profile system (save/load effect presets)
- Project system (full workflow persistence)
- Steam console snippet buttons

### Fixed
- GIF transparency handling
- JPG quality slider
- Multi-file naming collisions

---

## [1.3.0] - 2023-07-01

### Added
- GIF splitting with gifsicle
- Border templates (10 designs)
- Auto-enhance pipeline
- Batch folder processing

### Changed
- UI migrated to customtkinter
- Config now uses JSON with migration

---

## [1.2.0] - 2023-04-15

### Added
- Template system (Uniform, Multi, Single)
- PNG last-byte patch (0x21)
- Multi-part output naming
- Output format selection (PNG/JPG)

---

## [1.1.0] - 2023-01-20

### Added
- Basic image splitting (uniform)
- Template presets (Workshop 5, Artwork 2, Screenshot)
- Drag & drop support
- PNG/JPG output

---

## [1.0.0] - 2022-11-01

### Initial Release
- Basic 5-part vertical split
- Fixed 150×1250 template
- PNG output only

---

## Migration Guide

### From 1.x to 2.0

**Config Files**
- Old: `steam_splitter_config.json` → New: `%LOCALAPPDATA%\SplitForge\config.json`
- Auto-migrated on first run

**Templates**
- Built-in templates preserved
- Custom templates auto-migrated to new format

**Profiles/Projects**
- Not compatible with 1.x
- Recreate in Settings → Profiles/Projects

**Steam Settings**
- API keys, URLs preserved
- Browser profile path may need update
