"""core.py — LEGACY SHIM (deprecated)
Tüm mantık `src/steameditor/core/processor.py`'de yaşar.
Bu dosya sadece geriye uyum için kalır (`import core` → processor'a yönlenir).
Yeni kod `from steameditor.core.processor import ...` kullanmalı.
"""
import os
import sys
import types
import warnings

_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import steameditor.core.processor as _proc

warnings.warn(
    "core.py (kök) deprecated — `from steameditor.core.processor import ...` kullanın. "
    "Bu shim bir sonraki major sürümde kaldırılacak.",
    DeprecationWarning,
    stacklevel=2,
)

class _Proxy(types.ModuleType):
    def __getattr__(self, name):
        return getattr(_proc, name)
    def __setattr__(self, name, value):
        try:
            setattr(_proc, name, value)
        except Exception:
            pass
        super().__setattr__(name, value)

_proxy = _Proxy(__name__)
_proxy.__dict__.update(_proc.__dict__)
_proxy.__file__ = __file__
_proxy._proc = _proc
sys.modules[__name__] = _proxy
