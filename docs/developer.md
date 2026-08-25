# Developer Documentation

## 🏗️ Architecture Overview

### Core Principles
- **Separation of Concerns**: UI completely separated from business logic
- **Dependency Injection**: Services accessed via `get_*()` functions
- **Event-Driven**: Loose coupling via `EventBus`
- **Type Safety**: Pydantic models + strict pyright checking

### Entry Points
```python
# Main application
python -m steameditor

# GIF Maker (standalone)
python GIF/gif.py

# CLI (future)
python -m steameditor.cli --help
```

---

## 📦 Core Modules

### Models (`steameditor.core.models`)
```python
# Template definition
template = Template(
    name="My Template",
    mode="uniform",
    width=754,
    height=1250,
    parts=5,
    patch=True,
    prefix="work"
)

# Effect configuration
effects = EffectConfig(
    border_fx=BorderFXConfig(enabled=True, template="BorderDesign1.png"),
    text_overlay=TextOverlayConfig(enabled=True, text="My Art"),
    auto_enhance=AutoEnhanceConfig(enabled=True, intensity=50)
)
```

### Processor (`steameditor.core.processor`)
```python
# Simple processing
from steameditor.core import process_image
result = process_image("input.png", "output/", template, effects)

# With context (advanced)
ctx = ProcessingContext(
    source_path=Path("input.png"),
    template=template,
    effects=effects,
    output_dir=Path("output/")
)
result = process_image(ctx)

# Batch processing
from steameditor.core import process_folder
results = process_folder("input_folder/", "output/", template, effects)
```

### Configuration (`steameditor.services.config_service`)
```python
from steameditor.services import get_config_service

config = get_config_service()

# Read
template = config.templates[0]
output_dir = config.config.resolved_output_dir

# Write
config.update_config(output_dir="/new/path")
config.add_template(new_template)
```

---

## 🔌 Services

### Worker Pool
```python
from steameditor.services import get_worker_pool

pool = get_worker_pool()

# Submit task
future = pool.submit(heavy_function, arg1, arg2)
result = future.result()  # TaskResult(success=True, result=...)
```

### Image Cache
```python
from steameditor.services import get_image_cache, get_thumbnail

# Thumbnails
thumb = get_thumbnail("large_image.png", (256, 256))

# Full cache
cache = get_image_cache()
img = cache.get("image.png", (512, 512))
cache.put("image.png", img)
```

### Event Bus
```python
from steameditor.events import emit, subscribe

# Subscribe
sub_id = subscribe("image.loaded", lambda e: print(f"Loaded: {e.data}"))

# Emit
emit("image.loaded", {"path": "/path/to/image.png"})

# Unsubscribe
unsubscribe("image.loaded", sub_id)
```

---

## 🎨 UI Development

### Design System
```python
from steameditor.ui.design_system import COLORS, SPACING, TYPO, make_font

# Colors
bg = COLORS.bg_2
accent = COLORS.accent

# Fonts
title_font = make_font(TYPO.heading_lg)
body_font = make_font(TYPO.body_md)

# Spacing
pad = SPACING.md
```

### Custom Components
```python
from steameditor.ui.components import AnimButton, DropZone, StatusBar

# Animated button
btn = AnimButton(
    master,
    text="Click Me",
    variant="accent",  # "default" | "accent"
    command=callback
)

# Drop zone
drop = DropZone(
    master,
    on_file=handle_file,
    on_batch=handle_batch
)

# Status bar
status = StatusBar(master)
status.busy("Processing...")
status.ok("Done!")
```

---

## 🧪 Testing

### Unit Tests
```python
# tests/test_core.py
def test_resize_cover():
    img = Image.new("RGB", (800, 400))
    out = resize_cover(img, 300, 300)
    assert out.size == (300, 300)

def test_uniform_bounds():
    assert uniform_slice_bounds(754, 5) == [
        (0, 151), (151, 302), (302, 453), (453, 604), (604, 754)
    ]
```

### Integration Tests
```python
def test_process_image_uniform(tmp_path):
    src = tmp_path / "input.png"
    Image.new("RGB", (1508, 1000)).save(src)
    
    result = process_image(
        src, tmp_path / "out",
        TEMPLATES[0],  # Atölye 5-parça
        EffectConfig()
    )
    
    assert len(result) == 5
    for path in result:
        assert Path(path).exists()
```

---

## 📦 Adding New Features

### 1. Add Model
```python
# src/steameditor/core/models.py
class NewFeatureConfig(BaseModel):
    enabled: bool = False
    setting: str = "default"
```

### 2. Add Processor Logic
```python
# src/steameditor/core/processor.py
def apply_new_feature(img: Image.Image, cfg: NewFeatureConfig) -> Image.Image:
    if not cfg.enabled:
        return img
    # ... implementation
    return img
```

### 3. Add to EffectConfig
```python
class EffectConfig(BaseModel):
    # ... existing fields
    new_feature: NewFeatureConfig = Field(default_factory=NewFeatureConfig)
```

### 4. Add UI
```python
# src/steameditor/ui/pages/settings_page.py
def _build_settings(self, p):
    section("NEW FEATURE")
    enable_check("Enable Feature", "new_feature_enabled")
    # ... more controls
```

---

## 🔧 Code Style

### Imports
```python
# Standard library first
import os
import sys
from pathlib import Path
from typing import Optional, List

# Third-party
import customtkinter as ctk
from PIL import Image
from pydantic import BaseModel, Field

# Local
from steameditor.core.models import Template
from steameditor.services import get_config_service
```

### Type Hints
```python
# Always use type hints
def process_image(
    path: str | Path,
    outdir: Path,
    template: Template,
    cfg: EffectConfig | None = None
) -> list[Path]:
    ...
```

### Error Handling
```python
from steameditor.exceptions import ProcessingError, handle_exception

try:
    result = risky_operation()
except Exception as e:
    raise handle_exception(e, "Processing failed")
```

---

## 📋 Release Checklist

- [ ] All tests pass (`pytest`)
- [ ] Type check passes (`pyright`)
- [ ] Lint clean (`ruff check`)
- [ ] Version bumped in `pyproject.toml` and `src/steameditor/__init__.py`
- [ ] Changelog updated (`CHANGELOG.md`)
- [ ] Build executable (`python packaging/build.py`)
- [ ] Test installer (`makensis packaging/nsis/installer.nsi`)
- [ ] Create GitHub Release with artifacts

---

*Generated for SplitForge v2.0.0*