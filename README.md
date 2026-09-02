# SplitForge — Steam Showcase Studio

> Professional desktop tool for creating Steam Workshop showcase images with automated upload.

[![Version](https://img.shields.io/badge/version-2.4.0-blue.svg)](https://github.com/C4L1nn/steameditor/releases)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Build](https://github.com/C4L1nn/steameditor/actions/workflows/ci.yml/badge.svg)](https://github.com/C4L1nn/steameditor/actions)
[![Tests](https://img.shields.io/badge/tests-165%20passing-brightgreen.svg)](https://github.com/C4L1nn/steameditor/actions)

## ✨ Features

- **🎯 Precise Splitting**: Uniform (5-part Workshop), Multi (Artwork), Single (Screenshot)
- **✨ Effects Pipeline**: Border FX (10 templates + glow), Text Overlay (7 positions + drag), Auto-Enhance
- **📦 Batch Processing**: Folder processing, multi-band for tall images
- **🎮 Steam Integration**: Last-byte patch, console snippets, auto-upload via Playwright
- **💾 Project Management**: Save/load complete workflows (template + effects + upload URL)
- **🔄 Auto-Updates**: GitHub Releases integration with silent background checks

## 🚀 Quick Start

```bash
# Install from release
# Download SplitForge_Setup_2.0.0.exe from Releases

# Or run from source
pip install -r requirements.txt
python -m steameditor
```

## 🔐 Environment (AI Development)

`opencode.json` artık secret içermez — API anahtarı env var ile verilir:

```bash
cp .env.example .env
# .env içine NVIDIA_API_KEY=nvapi-... ekle
# opencode.json -> {env:NVIDIA_API_KEY} kullanır
```

> `opencode.json` ve `.env` `.gitignore`'da — asla commit etmeyin. Örnek: `opencode.json.example`.

## 📖 Documentation

- [User Guide](docs/user-guide.md)
- [Developer Docs](docs/developer.md)

## 🏗️ Architecture

```
src/steameditor/
├── core/           # Pure business logic (no UI deps)
│   ├── models.py   # Pydantic models (Template, EffectConfig, Profile, Project)
│   ├── processor.py# Image/GIF processing pipeline
│   └── uploader.py # Steam Community upload (Playwright)
├── services/       # Singleton services
│   ├── config_service.py
│   ├── worker_pool.py
│   ├── image_cache.py
│   └── log_service.py
├── ui/             # CustomTkinter UI
│   ├── app.py      # Main window
│   ├── components.py
│   ├── design_system.py
│   └── pages/
│       └── settings_page.py
├── events.py       # Event bus (pub/sub)
├── exceptions.py   # Custom exception hierarchy
├── config.py       # Legacy compat layer
└── __main__.py     # Entry point
```

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src/steameditor --cov-report=html --cov-fail-under=80

# Type checking
pyright src/steameditor/core src/steameditor/services src/steameditor/events.py src/steameditor/exceptions.py

# Linting
ruff check src/ tests/
ruff format --check src/ tests/
```

## 📦 Building

```bash
# Install build deps
pip install pyinstaller nsis

# Build executable
python packaging/build.py

# Build installer (requires NSIS)
makensis /DVERSION=2.0.0 packaging/nsis/installer.nsi
```

## 🤝 Contributing

1. Fork the repo
2. Create feature branch (`git checkout -b feature/amazing`)
2. Install pre-commit: `pre-commit install`
3. Make changes, add tests
4. Run checks: `pre-commit run --all-files`
5. Submit PR

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- [customtkinter](https://github.com/TomSchimansky/CustomTkinter) - Modern UI
- [Pillow](https://python-pillow.org/) - Image processing
- [Playwright](https://playwright.dev/python/) - Browser automation
- [Pydantic](https://docs.pydantic.dev/) - Data validation
- [gifsicle](https://www.lcdf.org/gifsicle/) - GIF optimization
- [ffmpeg](https://ffmpeg.org/) - Video → GIF/WebP

---

**Made with ❤️ for the Steam Workshop community**

[Report Bug](https://github.com/aykut/steameditor/issues) · [Request Feature](https://github.com/aykut/steameditor/issues/new)