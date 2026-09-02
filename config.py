"""config.py — LEGACY SHIM (deprecated)
Tüm mantık `src/steameditor/config_legacy.py`'de yaşar.
Bu dosya sadece geriye uyum için kalır (`import config` → config_legacy'ye yönlenir).
Yeni kod `from steameditor.config_legacy import ...` kullanmalı.
"""
import os
import sys
import types
import warnings

_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import steameditor.config_legacy as _cl

warnings.warn(
    "config.py (kök) deprecated — `from steameditor.config_legacy import ...` kullanın. "
    "Bu shim bir sonraki major sürümde kaldırılacak.",
    DeprecationWarning,
    stacklevel=2,
)

class _Proxy(types.ModuleType):
    def __getattr__(self, name):
        return getattr(_cl, name)
    def __setattr__(self, name, value):
        try:
            setattr(_cl, name, value)
        except Exception:
            pass
        super().__setattr__(name, value)

# Create proxy and replace sys.modules entry
_proxy = _Proxy(__name__)
_proxy.__dict__.update(_cl.__dict__)
_proxy.__file__ = __file__
_proxy._cl = _cl
sys.modules[__name__] = _proxy
