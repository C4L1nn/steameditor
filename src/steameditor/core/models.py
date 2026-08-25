"""steameditor.core.models — Pydantic models for type-safe configuration and data."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
from typing_extensions import Annotated


# ════════════════════════════════════════════════════════════════════
# Template Models
# ════════════════════════════════════════════════════════════════════

class MultiPart(BaseModel):
    """Single part definition for multi-mode templates."""
    width: Annotated[int, Field(gt=0, description="Part width in pixels")]
    height: Annotated[int, Field(gt=0, description="Part height in pixels")]


class DictLikeModel(BaseModel):
    """editor.py tarzı dict erişimi (t["anahtar"], t.get("anahtar")) için köprü."""

    def get(self, key: str, default=None):
        value = getattr(self, key, default)
        return default if value is None else value

    def __getitem__(self, key: str):
        try:
            return getattr(self, key)
        except AttributeError as exc:
            raise KeyError(key) from exc

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and hasattr(self, key)


class Template(DictLikeModel):
    """Steam showcase template definition."""
    name: Annotated[str, Field(min_length=1, description="Display name")]
    mode: Annotated[Literal["uniform", "multi", "single"], Field(description="Splitting mode")]
    width: Annotated[int, Field(gt=0, description="Target canvas width")]
    height: Annotated[int, Field(gt=0, description="Target canvas height")]
    parts: Annotated[int | list[MultiPart], Field(default=5, description="Part count (uniform) or part definitions (multi)")]
    patch: Annotated[bool, Field(default=False, description="Apply PNG last-byte patch (0x21)")]
    prefix: Annotated[str, Field(default="parca", min_length=1, description="Output filename prefix")]
    builtin: Annotated[bool, Field(default=False, description="Whether this is a built-in template")]

    @field_validator("parts", mode="before")
    @classmethod
    def _validate_parts(cls, v: int | list[dict[str, int]] | list[MultiPart], info) -> int | list[MultiPart]:
        mode = info.data.get("mode", "uniform")
        if mode == "uniform":
            return v if isinstance(v, int) and v > 0 else 5
        if mode == "multi":
            if isinstance(v, list):
                return [MultiPart(**p) if isinstance(p, dict) else p for p in v]
            return [MultiPart(width=506, height=1000), MultiPart(width=100, height=1000)]
        return 1

    @model_validator(mode="after")
    def _validate_consistency(self):
        if self.mode == "uniform" and not isinstance(self.parts, int):
            raise ValueError("Uniform mode requires integer parts count")
        if self.mode == "multi" and not isinstance(self.parts, list):
            raise ValueError("Multi mode requires list of part definitions")
        return self

    def get_parts_list(self) -> list[MultiPart]:
        """Normalize parts to list of MultiPart."""
        if self.mode == "uniform":
            count = self.parts if isinstance(self.parts, int) else 5
            part_w = self.width // count
            remainder = self.width % count
            parts = []
            for i in range(count):
                w = part_w + (1 if i < remainder else 0)
                parts.append(MultiPart(width=w, height=self.height))
            return parts
        if self.mode == "multi":
            return self.parts if isinstance(self.parts, list) else []
        return [MultiPart(width=self.width, height=self.height)]

    def get_uniform_bounds(self) -> list[tuple[int, int]]:
        """Calculate slice bounds for uniform mode (remainder distributed to first parts)."""
        if self.mode != "uniform":
            raise ValueError("Only valid for uniform mode")
        count = self.parts if isinstance(self.parts, int) else 5
        base = self.width // count
        rem = self.width % count
        bounds = []
        x = 0
        for i in range(count):
            w = base + (1 if i < rem else 0)
            bounds.append((x, x + w))
            x += w
        return bounds


# ════════════════════════════════════════════════════════════════════
# Effect Configuration
# ════════════════════════════════════════════════════════════════════

class BorderFXConfig(BaseModel):
    enabled: bool = False
    template: str = ""
    color: Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")] = "#8B5CF6"
    opacity: Annotated[int, Field(ge=0, le=100)] = 100
    glow: Annotated[int, Field(ge=0, le=100)] = 35


class TextOverlayConfig(BaseModel):
    enabled: bool = False
    text: str = ""
    color: Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")] = "#FFFFFF"
    size: Annotated[int, Field(ge=1, le=30)] = 6
    position: Annotated[
        Literal["Üst Sol", "Üst Orta", "Üst Sağ", "Alt Sol", "Alt Orta", "Alt Sağ", "Orta"],
        Field(default="Alt Orta")
    ] = "Alt Orta"
    opacity: Annotated[int, Field(ge=0, le=100)] = 100
    custom_pos: Optional[list[float]] = Field(default=None, description="[x_pct, y_pct] 0-1")


class AutoEnhanceConfig(BaseModel):
    enabled: bool = False
    intensity: Annotated[int, Field(ge=0, le=100)] = 50


class OutputConfig(BaseModel):
    format: Annotated[Literal["png", "jpg"], Field(default="png")]
    jpg_quality: Annotated[int, Field(ge=1, le=100)] = 90
    gif_lossy: Annotated[int, Field(ge=0, le=200)] = 30
    gif_colors: Annotated[int, Field(ge=2, le=256)] = 256


class EffectConfig(BaseModel):
    border_fx: BorderFXConfig = Field(default_factory=BorderFXConfig)
    text_overlay: TextOverlayConfig = Field(default_factory=TextOverlayConfig)
    auto_enhance: AutoEnhanceConfig = Field(default_factory=AutoEnhanceConfig)
    output: OutputConfig = Field(default_factory=lambda: OutputConfig())
    autocrop_enabled: bool = False


# ════════════════════════════════════════════════════════════════════
# Application Configuration
# ════════════════════════════════════════════════════════════════════

class SteamConfig(BaseModel):
    api_key: str = ""
    app_id: str = ""
    published_file_id: str = ""
    community_url: str = "https://steamcommunity.com/sharedfiles/edititem/767/3/"
    profile_dir: str = ""
    auto_submit: bool = False
    wait_after_upload_ms: Annotated[int, Field(ge=100, le=60000)] = 1200
    title_template: str = "\u200e "


class AppConfig(BaseModel):
    default_preset: str = "Atölye Vitrini 5-Parça (150×1250)"
    output_dir: str = ""
    last_input_dir: str = ""
    open_output_after_process: bool = False
    auto_upload: bool = False
    steam: SteamConfig = Field(default_factory=SteamConfig)
    multi_band_count: Annotated[int, Field(ge=1, le=20)] = 3
    onboarding_tips_shown: bool = False
    effects: EffectConfig = Field(default_factory=EffectConfig)

    @property
    def resolved_output_dir(self) -> Path:
        if self.output_dir and Path(self.output_dir).exists():
            return Path(self.output_dir)
        return Path.cwd() / "output"

    @property
    def resolved_profile_dir(self) -> Path:
        if self.steam.profile_dir:
            return Path(self.steam.profile_dir)
        return Path.cwd() / ".steam_browser_profile"


# ════════════════════════════════════════════════════════════════════
# Project & Profile Models
# ════════════════════════════════════════════════════════════════════

class Profile(BaseModel):
    name: Annotated[str, Field(min_length=1)]
    template_name: str
    effects: EffectConfig = Field(default_factory=EffectConfig)
    auto_upload: bool = False
    steam_community_auto_submit: bool = False
    created_at: float = 0
    updated_at: float = 0


class Project(BaseModel):
    name: Annotated[str, Field(min_length=1)]
    template_name: str
    output_dir: str
    note: str = ""
    steam_community_upload_url: Optional[str] = None
    steam_published_file_id: Optional[str] = None
    input_paths: list[str] = Field(default_factory=list)
    input_dir: Optional[str] = None
    effects: EffectConfig = Field(default_factory=EffectConfig)
    created_at: float = 0
    updated_at: float = 0

    def get_input_files(self) -> list[Path]:
        """Resolve all input files from paths or directory."""
        files = []
        for p in self.input_paths:
            path = Path(p)
            if path.is_file():
                files.append(path)
        if self.input_dir:
            dir_path = Path(self.input_dir)
            if dir_path.is_dir():
                for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
                    files.extend(dir_path.glob(f"*{ext}"))
                    files.extend(dir_path.glob(f"*{ext.upper()}"))
        return sorted(set(files))


# ════════════════════════════════════════════════════════════════════
# Processing Models
# ════════════════════════════════════════════════════════════════════

class ProcessingContext(BaseModel):
    """Immutable context passed to processing pipeline."""
    template: Template
    effects: EffectConfig
    output_dir: Path
    name_override: Optional[str] = None
    preset_origin: Optional[tuple[int, int]] = None
    region_scale: float = 1.0
    band_count: int = 1

    class Config:
        arbitrary_types_allowed = True


class ProcessingResult(BaseModel):
    success: bool
    files: list[Path] = Field(default_factory=list)
    error: Optional[str] = None
    template_name: str
    source_path: Optional[Path] = None
    processing_time_ms: float = 0

    class Config:
        arbitrary_types_allowed = True


# ════════════════════════════════════════════════════════════════════
# Built-in Templates Registry
# ════════════════════════════════════════════════════════════════════

BUILTIN_TEMPLATES: list[Template] = [
    Template(
        name="Atölye Vitrini 5-Parça (150×1250)",
        mode="uniform",
        width=754,
        height=1250,
        parts=5,
        patch=True,
        prefix="work",
        builtin=True,
    ),
    Template(
        name="Çizim Vitrini 2-Parça (506 + 100)",
        mode="multi",
        width=606,
        height=1000,
        parts=[MultiPart(width=506, height=1000), MultiPart(width=100, height=1000)],
        patch=False,
        prefix="art",
        builtin=True,
    ),
    Template(
        name="Ekran Görüntüsü Tek Parça (650×1000)",
        mode="single",
        width=650,
        height=1000,
        parts=1,
        patch=False,
        prefix="shot",
        builtin=True,
    ),
]

DEFAULT_TEMPLATE = BUILTIN_TEMPLATES[0]


# ════════════════════════════════════════════════════════════════════
# Template Utilities
# ════════════════════════════════════════════════════════════════════

def uniform_slice_bounds(total_w: int, parts: int) -> list[tuple[int, int]]:
    """Calculate vertical slice bounds for uniform template.
    Remainder pixels distributed to FIRST parts (Steam vitrini requirement: 754/5 -> 151,151,151,151,150)."""
    parts = max(1, int(parts))
    base = total_w // parts
    rem = total_w % parts
    bounds = []
    x = 0
    for i in range(parts):
        w = base + (1 if i < rem else 0)
        bounds.append((x, x + w))
        x += w
    return bounds