"""editor.py — LEGACY SHIM (deprecated)

Tüm UI mantığı `src/steameditor/ui/app_shell.py`'ye taşındı.
Bu dosya sadece geriye uyum için kalır (`python editor.py` veya `import editor`).

Strateji A: thin wrapper → AppShell
- `python editor.py <dosya>` → AppShell(preload_path)
- `python editor.py` (frozen headless) → headless_run
- `import editor; editor.App` → AppShell.App
"""
from __future__ import annotations

import os
import sys
import pathlib
import warnings

# src'yi sys.path'e ekle (kökten `python editor.py` çalışırken)
_SRC = pathlib.Path(__file__).parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

warnings.warn(
    "editor.py (kök) deprecated — `from steameditor.ui.app_shell import App` kullanın. "
    "Bu shim bir sonraki major sürümde kaldırılacak.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export modern App
from steameditor.ui.app_shell import App  # noqa: F401
from steameditor.ui.app_shell import App as AppShell  # noqa: F401
from steameditor.core.processor import process_image, process_folder, open_folder  # noqa: F401
from steameditor.config_legacy import TEMPLATES  # noqa: F401
from steameditor.services.log_service import get_logger  # noqa: F401

_log = get_logger("editor_shim")

# Legacy global (bazı eklentiler kontrol ediyor)
F12_ARMED = False  # noqa: F401

try:
    from steameditor.core.processor import _BORDER_DIR  # noqa: F401
except ImportError:
    _BORDER_DIR = ""  # type: ignore

# Headless (EXE drag-drop) — orijinal editor.py ile aynı davranış
def headless_run(target: str):
    """Frozen EXE'ye dosya sürükle-bırak: tek tıkla böl."""
    default_tmpl = TEMPLATES[0]
    if os.path.isfile(target):
        outdir = os.path.join(os.path.dirname(target), "output")
        process_image(target, outdir, default_tmpl)
    else:
        outdir = os.path.join(target, "output")
        process_folder(target, outdir, default_tmpl)
    _log.info(f"[DONE] Çıktı: {outdir}")
    open_folder(outdir)


def main():
    # Frozen headless
    if getattr(sys, "frozen", False) and len(sys.argv) > 1:
        t = sys.argv[1]
        if os.path.exists(t):
            headless_run(t)
            return
    preload = sys.argv[1] if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]) else None
    app = App(preload_path=preload)
    app.mainloop()


if __name__ == "__main__":
    main()
