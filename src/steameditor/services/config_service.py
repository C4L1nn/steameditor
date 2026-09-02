"""steameditor.services.config_service — Configuration management with schema validation."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Optional

from pydantic import ValidationError as PydanticValidationError

from steameditor.core.models import AppConfig, EffectConfig, SteamConfig, Template
from steameditor.events import emit, get_event_bus
from steameditor.exceptions import ConfigError, ValidationError, handle_exception


class ConfigService:
    """Singleton configuration service with validation, migration, and change notifications."""

    _instance: ConfigService | None = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._config: AppConfig = AppConfig()
        self._config_dir: Path = self._get_config_dir()
        self._config_file = self._config_dir / "config.json"
        self._presets_file = self._config_dir / "presets.json"
        self._profiles_file = self._config_dir / "profiles.json"
        self._projects_file = self._config_dir / "projects.json"
        self._history_file = self._config_dir / "history.json"
        self._recovery_file = self._config_dir / "recovery.json"
        self._templates: list[Template] = []
        self._load_all()
        self._initialized = True

    def _get_config_dir(self) -> Path:
        """Get platform-appropriate config directory."""
        # Windows: %LOCALAPPDATA%\SplitForge
        # Linux: ~/.config/splitforge
        # macOS: ~/Library/Application Support/SplitForge
        if os.name == "nt":
            base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        elif os.sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support"
        else:
            base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        config_dir = base / "SplitForge"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir

    @property
    def config_dir(self) -> Path:
        return self._config_dir

    @property
    def config(self) -> AppConfig:
        return self._config

    @property
    def templates(self) -> list[Template]:
        return self._templates

    # ═══════════════════════════════════════════════════════════════════
    # Loading
    # ═══════════════════════════════════════════════════════════════════

    def _load_all(self) -> None:
        """Load all configuration files."""
        self._load_config()
        self._load_templates()
        # Profiles, projects, history loaded on demand

    def _migrate_legacy_config(self) -> Path | None:
        """Varsa kök `steam_splitter_config.json`'u yeni konuma taşı."""
        # Proje kökü: src/steameditor/services -> 3 üst
        try:
            proj_root = Path(__file__).parents[3]
            legacy = proj_root / "steam_splitter_config.json"
            if legacy.is_file() and not self._config_file.exists():
                return legacy
        except Exception:
            pass
        return None

    def _legacy_to_appconfig(self, data: dict) -> dict:
        """Legacy flat dict -> AppConfig dict (Pydantic)."""
        # Map flat anahtarları nested yapıya
        mapped: dict[str, Any] = {}
        # Top-level
        for k in ("default_preset", "output_dir", "last_input_dir",
                  "open_output_after_process", "auto_upload",
                  "multi_band_count", "onboarding_tips_shown", "theme"):
            if k in data:
                mapped[k] = data[k]
        # Steam
        steam: dict[str, Any] = {}
        sm = {
            "steam_api_key": "api_key",
            "steam_app_id": "app_id",
            "steam_published_file_id": "published_file_id",
            "steam_community_upload_url": "community_url",
            "steam_community_profile_dir": "profile_dir",
            "steam_community_auto_submit": "auto_submit",
            "steam_community_wait_after_upload_ms": "wait_after_upload_ms",
            "steam_community_title_template": "title_template",
        }
        for old, new in sm.items():
            if old in data:
                steam[new] = data[old]
        if steam:
            mapped["steam"] = steam
        # Effects
        effects: dict[str, Any] = {}
        # border_fx
        bfx: dict[str, Any] = {}
        for old, new in [("border_fx_enabled", "enabled"),
                         ("border_fx_template", "template"),
                         ("border_fx_color", "color"),
                         ("border_fx_opacity", "opacity"),
                         ("border_fx_glow", "glow")]:
            if old in data:
                bfx[new] = data[old]
        if bfx:
            effects["border_fx"] = bfx
        # text_overlay
        tov: dict[str, Any] = {}
        for old, new in [("text_overlay_enabled", "enabled"),
                         ("text_overlay_text", "text"),
                         ("text_overlay_color", "color"),
                         ("text_overlay_size", "size"),
                         ("text_overlay_position", "position"),
                         ("text_overlay_opacity", "opacity"),
                         ("text_overlay_custom_pos", "custom_pos")]:
            if old in data:
                tov[new] = data[old]
        if tov:
            effects["text_overlay"] = tov
        # auto_enhance
        aen: dict[str, Any] = {}
        if "auto_enhance_enabled" in data:
            aen["enabled"] = data["auto_enhance_enabled"]
        if "auto_enhance_intensity" in data:
            aen["intensity"] = data["auto_enhance_intensity"]
        if aen:
            effects["auto_enhance"] = aen
        if "autocrop_enabled" in data:
            effects["autocrop_enabled"] = data["autocrop_enabled"]
        if "autocrop_mode" in data:
            effects["autocrop_mode"] = data["autocrop_mode"]
        # output
        out: dict[str, Any] = {}
        for old, new in [("output_format", "format"),
                         ("jpg_quality", "jpg_quality"),
                         ("gif_lossy", "gif_lossy"),
                         ("gif_colors", "gif_colors")]:
            if old in data:
                out[new] = data[old]
        if out:
            effects["output"] = out
        if effects:
            mapped["effects"] = effects
        return mapped

    def _load_config(self) -> None:
        """Load and validate main config (legacy migrasyon dahil)."""
        defaults = AppConfig()
        # Legacy migrasyon: yeni config yoksa kök dosyadan taşı
        if not self._config_file.exists():
            legacy_path = self._migrate_legacy_config()
            if legacy_path is not None:
                try:
                    legacy_data = json.loads(legacy_path.read_text(encoding="utf-8"))
                    mapped = self._legacy_to_appconfig(legacy_data)
                    merged = {**defaults.model_dump(), **mapped}
                    # Nested merge için steam/effects'i derin birleştir
                    if "steam" in mapped:
                        merged["steam"] = {**defaults.model_dump()["steam"], **mapped["steam"]}
                    if "effects" in mapped:
                        # effects alt dict'leri de derin birleştir
                        def _deep_merge(a, b):
                            res = dict(a)
                            for k, v in b.items():
                                if isinstance(v, dict) and isinstance(res.get(k), dict):
                                    res[k] = _deep_merge(res[k], v)
                                else:
                                    res[k] = v
                            return res
                        merged["effects"] = _deep_merge(defaults.model_dump()["effects"], mapped["effects"])
                    self._config = AppConfig(**merged)
                    self.save_config()
                    # Yedek kopya bırak (orijinali silme — shim hâlâ kullanıyor)
                    backup = legacy_path.with_suffix(".json.migrated")
                    try:
                        import shutil
                        shutil.copy2(legacy_path, backup)
                    except Exception:
                        pass
                    return
                except Exception as e:
                    # Migrasyon başarısız → varsayılanla devam
                    import logging
                    logging.getLogger("steameditor.config").warning(f"Legacy migrasyon hatası: {e}")
            self._config = defaults
            self.save_config()
            return

        try:
            data = json.loads(self._config_file.read_text(encoding="utf-8"))
            # Merge with defaults for backwards compatibility
            self._config = AppConfig(**{**defaults.model_dump(), **data})
        except (json.JSONDecodeError, PydanticValidationError) as e:
            # Backup corrupted config and start fresh
            backup = self._config_file.with_suffix(".json.bak")
            self._config_file.rename(backup)
            raise ConfigError(
                "Ayar dosyası bozuk, yedeklendi ve varsayılanlarla yeniden oluşturuldu.",
                f"Config load failed: {e}",
            )

    def _load_templates(self) -> None:
        """Load built-in + custom templates."""
        from steameditor.core.models import BUILTIN_TEMPLATES

        self._templates = list(BUILTIN_TEMPLATES)

        if not self._presets_file.exists():
            return

        try:
            data = json.loads(self._presets_file.read_text(encoding="utf-8"))
            existing_names = {t.name for t in self._templates}
            for p in data:
                name = p.get("name", "")
                if not name or name in existing_names:
                    continue
                mode = p.get("mode", "uniform")
                patch = p.get("last_byte", 0) != 0
                prefix = p.get("prefix", "cus")
                if mode == "multi":
                    parts = [
                        {"width": int(x.get("width", 100)), "height": int(x.get("height", 100))}
                        for x in p.get("parts", []) if isinstance(x, dict)
                    ]
                    if not parts:
                        continue
                    tmpl = Template(
                        name=name, mode="multi", parts=parts, patch=patch, prefix=prefix
                    )
                elif mode == "single":
                    tmpl = Template(
                        name=name, mode="single",
                        width=p.get("width", 650), height=p.get("height", 850),
                        patch=patch, prefix=prefix
                    )
                else:  # uniform
                    tmpl = Template(
                        name=name, mode="uniform",
                        width=p.get("width", 750), height=p.get("height", 1250),
                        parts=p.get("parts", 5), patch=patch, prefix=prefix
                    )
                self._templates.append(tmpl)
                existing_names.add(name)
        except Exception as e:
            raise ConfigError("Özel şablonlar yüklenemedi.", f"Preset load failed: {e}")

    # ═══════════════════════════════════════════════════════════════════
    # Saving
    # ═══════════════════════════════════════════════════════════════════

    def save_config(self) -> None:
        """Save current config to disk."""
        try:
            data = self._config.model_dump(mode="json")
            tmp = self._config_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self._config_file)
        except Exception as e:
            raise ConfigError("Ayarlar kaydedilemedi.", f"Config save failed: {e}")

    def save_templates(self) -> None:
        """Save custom (non-builtin) templates."""
        try:
            custom = []
            for t in self._templates:
                if t.builtin:
                    continue
                entry = {
                    "name": t.name,
                    "mode": t.mode,
                    "last_byte": 33 if t.patch else 0,
                    "prefix": t.prefix,
                }
                if t.mode == "multi":
                    entry["parts"] = [{"width": p.width, "height": p.height} for p in t.parts]
                else:
                    entry["width"] = t.width
                    entry["height"] = t.height
                    if t.mode == "uniform":
                        entry["parts"] = t.parts if isinstance(t.parts, int) else 5
                custom.append(entry)
            tmp = self._presets_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(custom, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self._presets_file)
        except Exception as e:
            raise ConfigError("Şablonlar kaydedilemedi.", f"Template save failed: {e}")

    # ═══════════════════════════════════════════════════════════════════
    # Config Mutations (with events)
    # ═══════════════════════════════════════════════════════════════════

    def update_config(self, **kwargs) -> None:
        """Update config fields and emit change event."""
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
        self.save_config()
        emit("config.changed", {"config": self._config.model_dump()})

    def update_effects(self, effects: EffectConfig) -> None:
        """Update effect configuration."""
        self._config.effects = effects
        self.save_config()
        emit("effects.changed", {"effects": effects.model_dump()})

    def set_template(self, template: Template) -> None:
        """Set active template."""
        # Config doesn't store template object, just name
        self._config.default_preset = template.name
        self.save_config()
        emit("template.changed", {"template": template.model_dump()})

    def add_template(self, template: Template) -> None:
        """Add custom template."""
        if any(t.name == template.name for t in self._templates):
            raise ValidationError(f"Şablon zaten var: {template.name}")
        self._templates.append(template)
        self.save_templates()
        emit("template.added", {"template": template.model_dump()})

    def update_template(self, template: Template) -> None:
        """Update existing custom template."""
        for i, t in enumerate(self._templates):
            if t.name == template.name:
                if t.builtin:
                    raise ValidationError("Yerleşik şablonlar düzenlenemez.")
                self._templates[i] = template
                self.save_templates()
                emit("template.updated", {"template": template.model_dump()})
                return
        raise ValidationError(f"Şablon bulunamadı: {template.name}")

    def delete_template(self, name: str) -> None:
        """Delete custom template."""
        for i, t in enumerate(self._templates):
            if t.name == name:
                if t.builtin:
                    raise ValidationError("Yerleşik şablonlar silinemez.")
                self._templates.pop(i)
                self.save_templates()
                emit("template.deleted", {"name": name})
                return
        raise ValidationError(f"Şablon bulunamadı: {name}")

    # ═══════════════════════════════════════════════════════════════════
    # Profiles
    # ═══════════════════════════════════════════════════════════════════

    def load_profiles(self) -> dict[str, Any]:
        if not self._profiles_file.exists():
            return {}
        try:
            return json.loads(self._profiles_file.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save_profiles(self, profiles: dict[str, Any]) -> None:
        try:
            tmp = self._profiles_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(profiles, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self._profiles_file)
        except Exception as e:
            raise ConfigError("Profiller kaydedilemedi.", f"Profile save failed: {e}")

    # ═══════════════════════════════════════════════════════════════════
    # Projects
    # ═══════════════════════════════════════════════════════════════════

    def load_projects(self) -> dict[str, Any]:
        if not self._projects_file.exists():
            return {}
        try:
            return json.loads(self._projects_file.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save_projects(self, projects: dict[str, Any]) -> None:
        try:
            tmp = self._projects_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(projects, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self._projects_file)
        except Exception as e:
            raise ConfigError("Projeler kaydedilemedi.", f"Project save failed: {e}")

    # ═══════════════════════════════════════════════════════════════════
    # History
    # ═══════════════════════════════════════════════════════════════════

    def load_history(self) -> list[dict]:
        if not self._history_file.exists():
            return []
        try:
            return json.loads(self._history_file.read_text(encoding="utf-8"))
        except Exception:
            return []

    def append_history(self, record: dict, limit: int = 200) -> None:
        records = self.load_history()
        records.append(record)
        records = records[-limit:]
        try:
            tmp = self._history_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self._history_file)
        except Exception:
            pass

    def clear_history(self) -> None:
        try:
            if self._history_file.exists():
                self._history_file.unlink()
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════
    # Recovery
    # ═══════════════════════════════════════════════════════════════════

    def save_recovery(self, state: dict) -> None:
        try:
            tmp = self._recovery_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self._recovery_file)
        except Exception:
            pass

    def load_recovery(self) -> Optional[dict]:
        if not self._recovery_file.exists():
            return None
        try:
            return json.loads(self._recovery_file.read_text(encoding="utf-8"))
        except Exception:
            return None

    def clear_recovery(self) -> None:
        try:
            if self._recovery_file.exists():
                self._recovery_file.unlink()
        except Exception:
            pass


# Global accessor
_config_service: ConfigService | None = None


def get_config_service() -> ConfigService:
    global _config_service
    if _config_service is None:
        _config_service = ConfigService()
    return _config_service