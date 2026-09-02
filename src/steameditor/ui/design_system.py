"""steameditor.ui.design_system — Modern, polished design system for SplitForge."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
import customtkinter as ctk
from PIL import Image


# ═══════════════════════════════════════════════════════════════════════
# COLOR SYSTEM — Modern, sophisticated palette with depth
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Colors:
    """Modern color palette with semantic meaning and depth (DARK default)."""

    # ── Base neutrals ──
    # Pure blacks/whites for extreme contrast
    pure_black: str = "#000000"
    pure_white: str = "#ffffff"

    # Deep surface hierarchy (6 levels) — DARK
    surface_0: str = "#030303"   # Deepest - app background
    surface_1: str = "#0a0a0b"   # Window chrome
    surface_2: str = "#111113"   # Primary panels
    surface_3: str = "#18181b"   # Cards, elevated
    surface_4: str = "#27272a"   # Inputs, hovers
    surface_5: str = "#3f3f46"   # Pressed, borders

    # Subtle variations for depth
    surface_raised: str = "#1f1f1f"    # Slightly raised
    surface_overlay: str = "#2a2a2e"   # Overlay/modal

    # ── Borders ──
    border_hairline: str = "#27272a"   # Subtle divider
    border_subtle: str = "#3f3f46"     # Default border
    border_default: str = "#52525b"    # Focus/active
    border_strong: str = "#71717a"     # High emphasis

    # ── Accent: Steam Orange (refined) ──
    accent_50: str = "#fff7ed"
    accent_100: str = "#ffedd5"
    accent_200: str = "#fed7aa"
    accent_300: str = "#fdba74"
    accent_400: str = "#fb923c"
    accent_500: str = "#f97316"   # Primary accent
    accent_600: str = "#ea580c"
    accent_700: str = "#c2410c"
    accent_800: str = "#9a3412"
    accent_900: str = "#7c2d12"

    # Semantic accents
    accent_glow: str = "#fb923c40"      # Subtle glow
    accent_glow_strong: str = "#fb923c80"
    accent_subtle: str = "#f973161a"    # Very subtle bg

    # ── Semantic colors (refined) ──
    success_50: str = "#f0fdf4"
    success_100: str = "#dcfce7"
    success_500: str = "#22c55e"
    success_600: str = "#16a34a"
    success_bg: str = "#22c55e1a"

    warning_50: str = "#fffbeb"
    warning_100: str = "#fef3c7"
    warning_500: str = "#f59e0b"
    warning_600: str = "#d97706"
    warning_bg: str = "#f59e0b1a"

    error_50: str = "#fef2f2"
    error_100: str = "#fee2e2"
    error_500: str = "#ef4444"
    error_600: str = "#dc2626"
    error_bg: str = "#ef44441a"

    info_50: str = "#eff6ff"
    info_100: str = "#dbeafe"
    info_500: str = "#3b82f6"
    info_600: str = "#2563eb"
    info_bg: str = "#3b82f61a"

    # ── Text hierarchy ──
    text_primary: str = "#fafafa"       # Highest contrast
    text_secondary: str = "#d4d4d8"     # Body text
    text_tertiary: str = "#a1a1aa"      # Secondary info
    text_muted: str = "#71717a"         # Placeholders, hints
    text_disabled: str = "#52525b"      # Disabled state
    text_inverse: str = "#09090b"       # On accent

    # ── Accent text ──
    text_accent: str = "#fb923c"
    text_success: str = "#4ade80"
    text_warning: str = "#fbbf24"
    text_error: str = "#f87171"
    text_info: str = "#60a5fa"

    # ── Glass/Frost ──
    glass_bg: str = "#ffffff08"          # 3% white
    glass_bg_strong: str = "#ffffff12"   # 7% white
    glass_border: str = "#ffffff1a"      # 10% white
    glass_shadow: str = "#00000040"      # Subtle shadow

    # ── Scrollbars ──
    scrollbar_track: str = "#00000000"   # Transparent
    scrollbar_thumb: str = "#52525b"     # Thumb
    scrollbar_thumb_hover: str = "#71717a"


@dataclass(frozen=True)
class LightColors(Colors):
    """Light theme — same keys, light surfaces (inherits accent/semantic)."""

    # Light surfaces (inverted hierarchy)
    surface_0: str = "#f8fafc"   # App bg — slate-50
    surface_1: str = "#f1f5f9"   # Window chrome — slate-100
    surface_2: str = "#ffffff"   # Primary panels — white
    surface_3: str = "#e2e8f0"   # Cards — slate-200
    surface_4: str = "#cbd5e1"   # Inputs — slate-300
    surface_5: str = "#94a3b8"   # Borders — slate-400
    surface_raised: str = "#ffffff"
    surface_overlay: str = "#f1f5f9"

    border_hairline: str = "#e2e8f0"
    border_subtle: str = "#cbd5e1"
    border_default: str = "#94a3b8"
    border_strong: str = "#64748b"

    # Text — dark on light
    text_primary: str = "#0f172a"       # slate-900
    text_secondary: str = "#334155"     # slate-700
    text_tertiary: str = "#475569"      # slate-600
    text_muted: str = "#94a3b8"         # slate-400
    text_disabled: str = "#cbd5e1"
    text_inverse: str = "#f8fafc"

    # Glass — dark on light
    glass_bg: str = "#00000008"
    glass_bg_strong: str = "#00000012"
    glass_border: str = "#0000001a"
    glass_shadow: str = "#00000020"

    scrollbar_thumb: str = "#cbd5e1"
    scrollbar_thumb_hover: str = "#94a3b8"


# ═══════════════════════════════════════════════════════════════════════
# SPACING SYSTEM — 4px base with harmonious scale
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Spacing:
    """Harmonious spacing scale (4px base, major third ratio ~1.25)."""
    none: int = 0
    xxxs: int = 2      # 2px - micro
    xxs: int = 4       # 4px - tight
    xs: int = 6        # 6px - compact
    sm: int = 8        # 8px - small
    md: int = 12       # 12px - default
    lg: int = 16       # 16px - comfortable
    xl: int = 24       # 24px - section
    xxl: int = 32      # 32px - major
    xxxl: int = 48     # 48px - hero
    xxxxl: int = 64    # 64px - massive


# ═══════════════════════════════════════════════════════════════════════
# TYPOGRAPHY — Modern scale with clear hierarchy
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Typography:
    """Typography scale with clear visual hierarchy."""

    # Font families
    font_family: str = "Segoe UI Variable"      # Primary (Windows 11+)
    font_family_fallback: str = "Segoe UI"       # Fallback
    font_family_mono: str = "JetBrains Mono"     # Monospace (code)
    font_family_mono_fallback: str = "Consolas"  # Fallback

    # Display (hero, landing)
    display_xl: tuple[int, str] = (40, "700")    # Hero
    display_lg: tuple[int, str] = (32, "700")    # Page title
    display_md: tuple[int, str] = (28, "600")    # Section hero
    display_sm: tuple[int, str] = (24, "600")    # Card hero

    # Headings
    heading_xl: tuple[int, str] = (22, "600")    # H1
    heading_lg: tuple[int, str] = (20, "600")    # H2
    heading_md: tuple[int, str] = (18, "600")    # H3
    heading_sm: tuple[int, str] = (16, "600")    # H4
    heading_xs: tuple[int, str] = (14, "600")    # H5

    # Body text
    body_xl: tuple[int, str] = (16, "400")       # Large body
    body_lg: tuple[int, str] = (15, "400")       # Lead
    body_md: tuple[int, str] = (14, "400")       # Default
    body_sm: tuple[int, str] = (13, "400")       # Compact
    body_xs: tuple[int, str] = (12, "400")       # Small

    # UI elements
    label_lg: tuple[int, str] = (13, "500")      # Form label
    label_md: tuple[int, str] = (12, "500")      # Default label
    label_sm: tuple[int, str] = (11, "500")      # Small label
    button_lg: tuple[int, str] = (14, "600")     # Large button
    button_md: tuple[int, str] = (13, "600")     # Default button
    button_sm: tuple[int, str] = (12, "600")     # Small button

    # Specialized
    caption: tuple[int, str] = (11, "400")       # Captions
    overline: tuple[int, str] = (10, "600")      # Category labels
    code: tuple[int, str] = (12, "400")          # Monospace / path
    code_sm: tuple[int, str] = (11, "400")       # Inline code
    code_md: tuple[int, str] = (12, "400")       # Code block
    mono_xs: tuple[int, str] = (10, "400")       # Tiny mono


# ═══════════════════════════════════════════════════════════════════════
# BORDER RADIUS — Modern rounded scale
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class BorderRadius:
    none: int = 0
    xs: int = 2       # Tiny
    sm: int = 4       # Subtle
    md: int = 6       # Default
    lg: int = 8       # Cards
    xl: int = 12      # Panels
    xxl: int = 16     # Modals
    xxxl: int = 24    # Hero
    full: int = 9999  # Pills, avatars


# ═══════════════════════════════════════════════════════════════════════
# SHADOWS & ELEVATION — Layered depth system
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Elevation:
    """Elevation system with consistent shadows."""
    # Format: (offset_x, offset_y, blur, spread, color)
    none: tuple = ()
    level_0: tuple = (0, 0, 0, 0, "#00000000")      # Flat
    level_1: tuple = (0, 1, 2, 0, "#0000001a")      # Subtle (cards)
    level_2: tuple = (0, 4, 8, -2, "#00000026")     # Raised (dropdowns)
    level_3: tuple = (0, 8, 16, -4, "#00000033")    # Floating (modals)
    level_4: tuple = (0, 16, 32, -8, "#00000040")   # High (toasts)
    level_5: tuple = (0, 24, 48, -12, "#00000050")  # Maximum (drawers)

    # Glow variants
    glow_subtle: tuple = (0, 0, 16, 0, "#f9731633")
    glow_medium: tuple = (0, 0, 24, 0, "#f973164d")
    glow_strong: tuple = (0, 0, 32, 0, "#f9731666")

    # Inner shadows (for pressed states)
    inner_subtle: tuple = (0, 2, 4, 0, "#00000040")
    inner_medium: tuple = (0, 4, 8, 0, "#00000060")


# ═══════════════════════════════════════════════════════════════════════
# ANIMATION & TRANSITION TOKENS
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Motion:
    """Animation tokens for consistent motion."""
    # Durations (ms)
    instant: int = 0
    fast: int = 100       # Micro-interactions
    normal: int = 150     # Default
    slow: int = 250       # Transitions
    slower: int = 350     # Modals, drawers
    slowest: int = 500    # Page transitions

    # Easing curves (CSS cubic-bezier equivalents)
    ease_linear: str = "linear"
    ease_out: str = "cubic-bezier(0.25, 0.46, 0.45, 0.94)"   # Standard out
    ease_in: str = "cubic-bezier(0.55, 0.05, 0.79, 0.26)"    # Standard in
    ease_in_out: str = "cubic-bezier(0.4, 0, 0.2, 1)"        # Material
    ease_spring: str = "cubic-bezier(0.34, 1.56, 0.64, 1)"   # Springy
    ease_bounce: str = "cubic-bezier(0.68, -0.55, 0.265, 1.55)"  # Bouncy

    # Specific use cases
    hover: int = 100
    press: int = 50
    focus: int = 100
    tooltip: int = 150
    toast: int = 200
    modal: int = 250
    drawer: int = 300


# ═══════════════════════════════════════════════════════════════════════
# Z-INDEX LAYERS
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ZIndex:
    """Semantic z-index layers."""
    base: int = 0
    content: int = 10
    raised: int = 20
    dropdown: int = 100
    sticky: int = 200
    fixed: int = 300
    modal_backdrop: int = 400
    modal: int = 500
    popover: int = 600
    tooltip: int = 700
    toast: int = 800
    max: int = 9999


# ═══════════════════════════════════════════════════════════════════════
# BREAKPOINTS (for future responsive needs)
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Breakpoints:
    xs: int = 0
    sm: int = 640
    md: int = 768
    lg: int = 1024
    xl: int = 1280
    xxl: int = 1536


# ═══════════════════════════════════════════════════════════════════════
# COMPONENT VARIANTS — Semantic component configurations
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ButtonVariant:
    """Button style variants."""
    # Primary - main actions
    primary: dict = None

    # Secondary - alternative actions
    secondary: dict = None

    # Outline - subtle actions
    outline: dict = None

    # Ghost - minimal actions
    ghost: dict = None

    # Danger - destructive
    danger: dict = None

    # Success - positive actions
    success: dict = None

    def __post_init__(self):
        c = COLORS
        object.__setattr__(self, "primary", {
            "bg": c.accent_500, "hover": c.accent_600, "active": c.accent_700,
            "text": c.pure_white, "border": "transparent",
            "shadow": "level_1", "glow": "glow_subtle"
        })
        object.__setattr__(self, "secondary", {
            "bg": c.surface_3, "hover": c.surface_4, "active": c.surface_5,
            "text": c.text_primary, "border": c.border_default,
            "shadow": "level_1"
        })
        object.__setattr__(self, "outline", {
            "bg": "transparent", "hover": c.accent_subtle, "active": c.accent_glow,
            "text": c.accent_500, "border": c.accent_500,
            "shadow": "none"
        })
        object.__setattr__(self, "ghost", {
            "bg": "transparent", "hover": c.surface_2, "active": c.surface_3,
            "text": c.text_secondary, "border": "transparent",
            "shadow": "none"
        })
        object.__setattr__(self, "danger", {
            "bg": c.error_500, "hover": c.error_600, "active": c.error_600,
            "text": c.pure_white, "border": "transparent",
            "shadow": "level_1", "glow": "none"
        })
        object.__setattr__(self, "success", {
            "bg": c.success_500, "hover": c.success_600, "active": c.success_600,
            "text": c.pure_white, "border": "transparent",
            "shadow": "level_1", "glow": "none"
        })


@dataclass(frozen=True)
class InputVariant:
    """Input field variants."""
    default: dict = None
    filled: dict = None
    outlined: dict = None
    underlined: dict = None

    def __post_init__(self):
        c = COLORS
        object.__setattr__(self, "default", {
            "bg": c.surface_3, "hover": c.surface_4, "focus": c.surface_4,
            "text": c.text_primary, "placeholder": c.text_muted,
            "border": c.border_subtle, "focus_border": c.accent_500,
            "error_border": c.error_500, "shadow": "level_1"
        })
        object.__setattr__(self, "filled", {
            "bg": c.surface_2, "hover": c.surface_3, "focus": c.surface_3,
            "text": c.text_primary, "placeholder": c.text_muted,
            "border": "transparent", "focus_border": c.accent_500,
            "error_border": c.error_500, "shadow": "level_1"
        })
        object.__setattr__(self, "outlined", {
            "bg": "transparent", "hover": c.surface_1, "focus": "transparent",
            "text": c.text_primary, "placeholder": c.text_muted,
            "border": c.border_default, "focus_border": c.accent_500,
            "error_border": c.error_500, "shadow": "none"
        })
        object.__setattr__(self, "underlined", {
            "bg": "transparent", "hover": "transparent", "focus": "transparent",
            "text": c.text_primary, "placeholder": c.text_muted,
            "border": "transparent", "bottom_border": c.border_subtle,
            "focus_border": c.accent_500, "error_border": c.error_500,
            "shadow": "none"
        })


@dataclass(frozen=True)
class CardVariant:
    """Card/elevated surface variants."""
    default: dict = None
    elevated: dict = None
    outlined: dict = None
    filled: dict = None
    glass: dict = None

    def __post_init__(self):
        c = COLORS
        s = SHADOWS  # Use SHADOWS (the Elevation instance)
        object.__setattr__(self, "default", {
            "bg": c.surface_2, "border": c.border_subtle, "shadow": "level_1",
            "radius": "lg", "padding": "lg"
        })
        object.__setattr__(self, "elevated", {
            "bg": c.surface_2, "border": c.border_subtle, "shadow": "level_2",
            "radius": "xl", "padding": "lg"
        })
        object.__setattr__(self, "outlined", {
            "bg": "transparent", "border": c.border_default, "shadow": "none",
            "radius": "lg", "padding": "lg"
        })
        object.__setattr__(self, "filled", {
            "bg": c.surface_3, "border": c.border_subtle, "shadow": "level_1",
            "radius": "lg", "padding": "lg"
        })
        object.__setattr__(self, "glass", {
            "bg": c.glass_bg, "border": c.glass_border, "shadow": "level_2",
            "radius": "xl", "padding": "lg", "blur": True
        })


# ═══════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCES
# ═══════════════════════════════════════════════════════════════════════

# ── Legacy aliases (editor.py / ui_theme.py paleti ile uyum) ──

def _alias_colors(cls):
    def prop(name):
        return property(lambda self: getattr(self, name))
    mapping = {
        "bg_0": "surface_0", "bg_1": "surface_1", "bg_2": "surface_2",
        "bg_3": "surface_3", "bg_4": "surface_4", "bg_5": "surface_5",
        "accent": "accent_500", "accent_hover": "accent_600",
        "accent_active": "accent_700",
        "success": "success_500", "error": "error_500",
        "error_active": "error_600", "warning": "warning_500",
        "info": "info_500",
    }
    for alias, target in mapping.items():
        setattr(cls, alias, prop(target))
    return cls


@_alias_colors
class _ColorsAliased(Colors):
    pass


@_alias_colors
class _LightColorsAliased(LightColors):
    pass


# Global theme state
_DARK_COLORS: _ColorsAliased = _ColorsAliased()
_LIGHT_COLORS: _LightColorsAliased = _LightColorsAliased()
_THEMES: dict[str, Colors] = {"dark": _DARK_COLORS, "light": _LIGHT_COLORS}
_CURRENT_THEME: str = "dark"


class _ColorsProxy:
    """Proxy so `from design_system import COLORS` stays live after theme switch."""

    def __getattr__(self, name: str):
        return getattr(_THEMES[_CURRENT_THEME], name)

    def __dir__(self):
        return dir(_THEMES[_CURRENT_THEME])


COLORS: Colors = _ColorsProxy()  # type: ignore
SPACING = Spacing()
TYPO = Typography()
RADIUS = BorderRadius()
SHADOWS = Elevation()  # Renamed from Shadows
MOTION = Motion()
Z_INDEX = ZIndex()
BREAKPOINTS = Breakpoints()
BUTTON = ButtonVariant()
INPUT = InputVariant()
CARD = CardVariant()


def get_theme() -> str:
    return _CURRENT_THEME


def get_colors(theme: str | None = None) -> Colors:
    if theme is None:
        # Return concrete colors for current theme (or proxy)
        return _THEMES[_CURRENT_THEME]
    return _THEMES.get(theme, _DARK_COLORS)


def set_theme(theme: str) -> Colors:
    """Tema değiştir — COLORS proxy otomatik güncellenir."""
    global _CURRENT_THEME
    if theme == "system":
        theme = "dark"
    if theme not in _THEMES:
        theme = "dark"
    _CURRENT_THEME = theme
    apply_theme(theme)
    return _THEMES[theme]


def toggle_theme() -> str:
    return set_theme("light" if _CURRENT_THEME == "dark" else "dark")


# ═══════════════════════════════════════════════════════════════════════
# THEME APPLICATION
# ═══════════════════════════════════════════════════════════════════════

def apply_theme(theme: str | None = None):
    """Apply the complete theme to customtkinter."""
    global _CURRENT_THEME
    if theme and theme in _THEMES:
        _CURRENT_THEME = theme
        c = _THEMES[theme]
    else:
        c = _THEMES[_CURRENT_THEME]

    ctk.set_appearance_mode("dark" if c is _DARK_COLORS else "light")
    ctk.set_default_color_theme("dark-blue")

    # Core overrides
    ctk.ThemeManager.theme["CTkFrame"]["fg_color"] = c.surface_2
    ctk.ThemeManager.theme["CTkFrame"]["border_color"] = c.border_subtle
    ctk.ThemeManager.theme["CTkFrame"]["border_width"] = 1
    ctk.ThemeManager.theme["CTkFrame"]["corner_radius"] = RADIUS.lg

    # Buttons
    ctk.ThemeManager.theme["CTkButton"]["fg_color"] = c.accent_500
    ctk.ThemeManager.theme["CTkButton"]["hover_color"] = c.accent_600
    ctk.ThemeManager.theme["CTkButton"]["text_color"] = c.pure_white
    ctk.ThemeManager.theme["CTkButton"]["text_color_disabled"] = c.text_disabled
    ctk.ThemeManager.theme["CTkButton"]["corner_radius"] = RADIUS.md
    ctk.ThemeManager.theme["CTkButton"]["border_width"] = 0
    ctk.ThemeManager.theme["CTkButton"]["height"] = 40

    # Entries
    ctk.ThemeManager.theme["CTkEntry"]["fg_color"] = COLORS.surface_3
    ctk.ThemeManager.theme["CTkEntry"]["border_color"] = COLORS.border_subtle
    ctk.ThemeManager.theme["CTkEntry"]["text_color"] = COLORS.text_primary
    ctk.ThemeManager.theme["CTkEntry"]["placeholder_text_color"] = COLORS.text_muted
    ctk.ThemeManager.theme["CTkEntry"]["corner_radius"] = RADIUS.md
    ctk.ThemeManager.theme["CTkEntry"]["height"] = 36
    ctk.ThemeManager.theme["CTkEntry"]["border_width"] = 1

    # Labels
    ctk.ThemeManager.theme["CTkLabel"]["text_color"] = COLORS.text_primary

    # Checkboxes/Radios
    ctk.ThemeManager.theme["CTkCheckBox"]["fg_color"] = COLORS.accent_500
    ctk.ThemeManager.theme["CTkCheckBox"]["hover_color"] = COLORS.accent_600
    ctk.ThemeManager.theme["CTkCheckBox"]["checkmark_color"] = COLORS.pure_white
    ctk.ThemeManager.theme["CTkCheckBox"]["border_color"] = COLORS.border_default
    ctk.ThemeManager.theme["CTkRadioButton"]["fg_color"] = COLORS.accent_500
    ctk.ThemeManager.theme["CTkRadioButton"]["hover_color"] = COLORS.accent_600

    # Switches
    ctk.ThemeManager.theme["CTkSwitch"]["fg_color"] = COLORS.border_default
    ctk.ThemeManager.theme["CTkSwitch"]["progress_color"] = COLORS.accent_500
    ctk.ThemeManager.theme["CTkSwitch"]["button_color"] = COLORS.pure_white
    ctk.ThemeManager.theme["CTkSwitch"]["button_hover_color"] = COLORS.accent_100

    # Sliders
    ctk.ThemeManager.theme["CTkSlider"]["fg_color"] = COLORS.surface_4
    ctk.ThemeManager.theme["CTkSlider"]["progress_color"] = COLORS.accent_500
    ctk.ThemeManager.theme["CTkSlider"]["button_color"] = COLORS.accent_500
    ctk.ThemeManager.theme["CTkSlider"]["button_hover_color"] = COLORS.accent_600
    ctk.ThemeManager.theme["CTkSlider"]["button_corner_radius"] = RADIUS.full

    # OptionMenu
    ctk.ThemeManager.theme["CTkOptionMenu"]["fg_color"] = COLORS.surface_3
    ctk.ThemeManager.theme["CTkOptionMenu"]["button_color"] = COLORS.accent_500
    ctk.ThemeManager.theme["CTkOptionMenu"]["button_hover_color"] = COLORS.accent_600
    ctk.ThemeManager.theme["CTkOptionMenu"]["dropdown_fg_color"] = COLORS.surface_3
    ctk.ThemeManager.theme["CTkOptionMenu"]["dropdown_hover_color"] = COLORS.surface_4
    ctk.ThemeManager.theme["CTkOptionMenu"]["text_color"] = COLORS.text_primary
    ctk.ThemeManager.theme["CTkOptionMenu"]["dropdown_text_color"] = COLORS.text_primary
    ctk.ThemeManager.theme["CTkOptionMenu"]["corner_radius"] = RADIUS.md

    # ScrollableFrame
    try:
        ctk.ThemeManager.theme["CTkScrollableFrame"]["fg_color"] = "transparent"
        ctk.ThemeManager.theme["CTkScrollableFrame"]["scrollbar_button_color"] = COLORS.surface_4
        ctk.ThemeManager.theme["CTkScrollableFrame"]["scrollbar_button_hover_color"] = COLORS.accent_500
        ctk.ThemeManager.theme["CTkScrollableFrame"]["corner_radius"] = RADIUS.lg
    except KeyError:
        pass

    # Scrollbar
    try:
        ctk.ThemeManager.theme["CTkScrollbar"]["button_color"] = COLORS.surface_4
        ctk.ThemeManager.theme["CTkScrollbar"]["button_hover_color"] = COLORS.accent_500
    except KeyError:
        pass

    # Tabs (CTkTabview) — may not exist in older customtkinter
    try:
        ctk.ThemeManager.theme["CTkTabview"]["fg_color"] = COLORS.surface_1
        ctk.ThemeManager.theme["CTkTabview"]["segmented_button_fg_color"] = COLORS.surface_3
        ctk.ThemeManager.theme["CTkTabview"]["segmented_button_selected_color"] = COLORS.accent_500
        ctk.ThemeManager.theme["CTkTabview"]["segmented_button_selected_hover_color"] = COLORS.accent_600
        ctk.ThemeManager.theme["CTkTabview"]["segmented_button_unselected_color"] = COLORS.surface_3
        ctk.ThemeManager.theme["CTkTabview"]["segmented_button_unselected_hover_color"] = COLORS.surface_4
        ctk.ThemeManager.theme["CTkTabview"]["text_color"] = COLORS.text_primary
        ctk.ThemeManager.theme["CTkTabview"]["segmented_button_corner_radius"] = RADIUS.md
    except KeyError:
        pass


# ═══════════════════════════════════════════════════════════════════════
# FONT & COLOR HELPERS
# ═══════════════════════════════════════════════════════════════════════

def make_font(style: tuple[int, str] | None = None, mono: bool = False,
              weight: str | None = None, size: int | None = None) -> ctk.CTkFont:
    """Create a CTkFont from style tuple (weight/size ile override edilebilir)."""
    if style is None:
        style = TYPO.body_md
    fsize, fweight = style
    family = TYPO.font_family_mono if mono else TYPO.font_family
    fweight = weight or fweight
    if size is not None:
        fsize = size
    # tkinter yalnızca "normal" / "bold" kabul eder; sayısal ağırlıkları eşle
    if isinstance(fweight, str) and fweight.isdigit():
        fweight = "bold" if int(fweight) >= 600 else "normal"
    return ctk.CTkFont(family, fsize, fweight)


def lerp_color(c1: str, c2: str, t: float) -> str:
    """Linear interpolation between two hex colors."""
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def apply_glass(widget: ctk.CTkBaseClass, intensity: Literal["subtle", "normal", "strong"] = "normal"):
    """Apply glassmorphism effect to a widget."""
    alpha = {"subtle": "08", "normal": "12", "strong": "1a"}[intensity]
    bg = f"#ffffff{alpha}"
    border = f"#ffffff1a"
    widget.configure(fg_color=bg, border_color=f"#ffffff1a", border_width=1)


def apply_elevation(widget: ctk.CTkBaseClass, level: Literal[0, 1, 2, 3, 4, 5] = 1):
    """Apply elevation shadow to widget."""
    # Note: customtkinter doesn't support box-shadow directly
    # This would need custom widget implementation
    pass


def make_ctk_image(img: Image.Image, size: tuple[int, int] | None = None) -> ctk.CTkImage:
    """Convert PIL image to CTkImage with HiDPI support."""
    if size is None:
        size = img.size
    return ctk.CTkImage(light_image=img, dark_image=img, size=size)


# ═══════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════