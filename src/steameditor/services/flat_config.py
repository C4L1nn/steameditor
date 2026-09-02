"""steameditor.services.flat_config — Pydantic AppConfig üzerine eski tarz
düz-dict (flat) erişim arayüzü.

editor.py'den taşınan UI kodu cfg'yi `cfg["anahtar"]` / `cfg.get("anahtar")`
ile kullanır; process_image de düz dict bekler. Bu adaptör okuma/yazmayı
AppConfig + EffectConfig alanlarına eşler; bilinmeyen anahtarlar extras'ta
tutulur. Yazmalar anında modele işlenir, kalıcılık için ConfigService.
save_config() çağrısı yeterlidir.
"""

from __future__ import annotations

from collections.abc import Iterator, MutableMapping
from typing import Any

from steameditor.core.models import AppConfig


# flat anahtar -> AppConfig üzerindeki alan yolu
_FIELD_MAP: dict[str, tuple[str, ...]] = {
    "autocrop_enabled": ("effects", "autocrop_enabled"),
    "border_fx_enabled": ("effects", "border_fx", "enabled"),
    "border_fx_template": ("effects", "border_fx", "template"),
    "border_fx_color": ("effects", "border_fx", "color"),
    "border_fx_opacity": ("effects", "border_fx", "opacity"),
    "border_fx_glow": ("effects", "border_fx", "glow"),
    "text_overlay_enabled": ("effects", "text_overlay", "enabled"),
    "text_overlay_text": ("effects", "text_overlay", "text"),
    "text_overlay_color": ("effects", "text_overlay", "color"),
    "text_overlay_size": ("effects", "text_overlay", "size"),
    "text_overlay_position": ("effects", "text_overlay", "position"),
    "text_overlay_opacity": ("effects", "text_overlay", "opacity"),
    "text_overlay_custom_pos": ("effects", "text_overlay", "custom_pos"),
    "auto_enhance_enabled": ("effects", "auto_enhance", "enabled"),
    "auto_enhance_intensity": ("effects", "auto_enhance", "intensity"),
    # Output
    "output_format": ("effects", "output", "format"),
    "jpg_quality": ("effects", "output", "jpg_quality"),
    "gif_lossy": ("effects", "output", "gif_lossy"),
    "gif_colors": ("effects", "output", "gif_colors"),
    # Steam
    "steam_api_key": ("steam", "api_key"),
    "steam_app_id": ("steam", "app_id"),
    "steam_published_file_id": ("steam", "published_file_id"),
    "steam_community_upload_url": ("steam", "community_url"),
    "steam_community_profile_dir": ("steam", "profile_dir"),
    "steam_community_auto_submit": ("steam", "auto_submit"),
    "steam_community_wait_after_upload_ms": ("steam", "wait_after_upload_ms"),
    "steam_community_title_template": ("steam", "title_template"),
}

_TOP_FIELDS = {
    "default_preset", "output_dir", "last_input_dir",
    "open_output_after_process", "auto_upload", "multi_band_count",
    "onboarding_tips_shown",
}


class FlatConfig(MutableMapping):
    """AppConfig'i eski tarz flat-dict gibi kullanmayı sağlar."""

    def __init__(self, config: AppConfig):
        self._config = config
        self._extras: dict[str, Any] = {}

    @property
    def model(self) -> AppConfig:
        return self._config

    def _resolve(self, key: str):
        """(parent_obj, last_attr) döndürür ya da None."""
        if key in _FIELD_MAP:
            path = _FIELD_MAP[key]
            obj = self._config
            for part in path[:-1]:
                obj = getattr(obj, part)
            return obj, path[-1]
        if key in _TOP_FIELDS:
            return self._config, key
        return None

    def __getitem__(self, key: str) -> Any:
        target = self._resolve(key)
        if target is None:
            return self._extras[key]
        obj, attr = target
        return getattr(obj, attr)

    def __setitem__(self, key: str, value: Any) -> None:
        target = self._resolve(key)
        if target is None:
            self._extras[key] = value
            return
        obj, attr = target
        try:
            setattr(obj, attr, value)
        except Exception:
            # model validasyonu reddederse extras'a düş (UI akışı bozulmasın)
            self._extras[key] = value

    def __delitem__(self, key: str) -> None:
        if key in self._extras:
            del self._extras[key]
        else:
            raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        yield from _FIELD_MAP
        yield from _TOP_FIELDS
        yield from self._extras

    def __len__(self) -> int:
        return len(_FIELD_MAP) + len(_TOP_FIELDS) + len(self._extras)

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        return key in _FIELD_MAP or key in _TOP_FIELDS or key in self._extras

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default
