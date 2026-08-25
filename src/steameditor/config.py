"""steameditor.config — Legacy config module for backward compatibility.

This module re-exports all functions from config_legacy for backward
compatibility with existing code that imports from steameditor.config.
"""

from steameditor.core.models import (
    Template,
    MultiPart,
    BUILTIN_TEMPLATES,
    DEFAULT_TEMPLATE,
    uniform_slice_bounds,
)

from steameditor.core.processor import (
    list_border_templates,
    render_template_preview,
    template_output_summary,
    render_showcase_preview,
)

from steameditor.config_legacy import (
    STEAM_HELPER_LINKS,
    STEAM_CONSOLE_SNIPPETS,
    STEAM_UPLOAD_STEPS,
    STEAM_DIRECT_UPLOAD_NOTE,
    TEMPLATE_SNIPPET_HINTS,
    load_custom_presets,
    save_custom_presets,
    load_profiles,
    save_profiles,
    load_projects,
    save_projects,
    load_history,
    append_history,
    clear_history,
    save_recovery,
    load_recovery,
    clear_recovery,
    load_config,
    save_config,
    steam_api_config_errors,
    clear_text_overlay_custom_pos,
    get_template_console_snippet,
    build_steam_upload_manifest,
    upload_status_path,
    PROFILE_KEYS,
)

# Constants from core.models
BUILTIN_TEMPLATES = BUILTIN_TEMPLATES
TEMPLATES = BUILTIN_TEMPLATES  # Legacy alias
DEFAULT_TEMPLATE = DEFAULT_TEMPLATE

# Constants from config_legacy
STEAM_HELPER_LINKS = STEAM_HELPER_LINKS
STEAM_CONSOLE_SNIPPETS = STEAM_CONSOLE_SNIPPETS
STEAM_UPLOAD_STEPS = STEAM_UPLOAD_STEPS
STEAM_DIRECT_UPLOAD_NOTE = STEAM_DIRECT_UPLOAD_NOTE
TEMPLATE_SNIPPET_HINTS = TEMPLATE_SNIPPET_HINTS
PROFILE_KEYS = PROFILE_KEYS

# Functions
load_custom_presets = load_custom_presets
save_custom_presets = save_custom_presets
load_profiles = load_profiles
save_profiles = save_profiles
load_projects = load_projects
save_projects = save_projects
load_history = load_history
append_history = append_history
clear_history = clear_history
save_recovery = save_recovery
load_recovery = load_recovery
clear_recovery = clear_recovery
load_config = load_config
save_config = save_config
steam_api_config_errors = steam_api_config_errors
clear_text_overlay_custom_pos = clear_text_overlay_custom_pos
get_template_console_snippet = get_template_console_snippet
build_steam_upload_manifest = build_steam_upload_manifest
upload_status_path = upload_status_path

__all__ = [
    # Constants
    "STEAM_HELPER_LINKS",
    "STEAM_CONSOLE_SNIPPETS",
    "STEAM_UPLOAD_STEPS",
    "STEAM_DIRECT_UPLOAD_NOTE",
    "TEMPLATE_SNIPPET_HINTS",
    "BUILTIN_TEMPLATES",
    "TEMPLATES",
    "DEFAULT_TEMPLATE",
    "PROFILE_KEYS",
    # Template functions
    "load_custom_presets",
    "save_custom_presets",
    "load_profiles",
    "save_profiles",
    "load_projects",
    "save_projects",
    "load_history",
    "append_history",
    "clear_history",
    # Recovery
    "save_recovery",
    "load_recovery",
    "clear_recovery",
    # Config
    "load_config",
    "save_config",
    "steam_api_config_errors",
    "clear_text_overlay_custom_pos",
    "get_template_console_snippet",
    "build_steam_upload_manifest",
    "upload_status_path",
    "PROFILE_KEYS",
]