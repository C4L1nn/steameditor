"""config.py — Steam Splitter PRO ayarlar / preset / Steam metadata katmanı.

editor.py bu modülden import eder. Tkinter'a bağlı değildir.
"""
import os
import json
import urllib.parse
import urllib.request

from applog import get_logger

_log = get_logger("config")


# ==========================================================
#   ŞABLONLAR (3 temel vitrin)
# ==========================================================

TEMPLATES = [
    {
        "name": "Workshop 5-Parça (Otomatik Boyut)",
        "mode": "uniform",       # 5 eşit dikey parça
        "width": 750,            # hedef canvas genişlik (5x150)
        "height": 1250,          # Varsayılan referans (artık dinamik değişiyor)
        "parts": 5,
        "patch": True,
        "prefix": "work"
    },
    {
        "name": "Çizim Vitrini 2-Parça (506 + 100)",
        "mode": "multi",         # her parça farklı boyut
        "parts": [
            {"width": 506, "height": 800},
            {"width": 100, "height": 800},
        ],
        "patch": False,
        "prefix": "art"
    },
    {
        "name": "Ekran Görüntüsü Tek Parça (650x850)",
        "mode": "single",        # tek çıktı
        "width": 650,
        "height": 850,
        "patch": False,
        "prefix": "shot"
    },
]


STEAM_HELPER_LINKS = [
    ("Çizim / Ekran Görüntüsü", "https://steamcommunity.com/sharedfiles/edititem/767/3/"),
    ("Atölye Vitrini", "https://steamcommunity.com/sharedfiles/filedetails/?id=2174159512"),
    ("Steam Design", "https://steam.design/"),
    ("HexEd.it", "https://hexed.it/"),
    ("EzGIF", "https://ezgif.com/"),
]


STEAM_CONSOLE_SNIPPETS = [
    (
        "Çizim vitrini boyut hilesi",
        "$J('#image_width').val(1000).attr('id',''),$J('#image_height').val(1).attr('id','');"
    ),
    (
        "Ekran görüntüsü file_type",
        "$J('#image_width').val('1000');$J('#image_height').val('1');$J('[name=\"file_type\"]').val(\"5\");"
    ),
    (
        "Atölye vitrini ayarları",
        "$J('[name=consumer_app_id]').val(480);$J('[name=file_type]').val(0);$J('[name=visibility]').val(0);"
    ),
]


STEAM_UPLOAD_STEPS = [
    "Görseli doğru şablonla böl",
    "Workshop parçalarında son byte patch kontrolü yap",
    "Steam sayfasını aç ve F12/console alanını hazırla",
    "İlgili console kodunu yapıştır",
    "Parçaları sırayla yükle ve görünürlüğü kontrol et",
]


STEAM_PUBLISHED_FILE_DETAILS_URL = (
    "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
)


STEAM_DIRECT_UPLOAD_NOTE = (
    "Steam Web API, lokal PNG/GIF dosyalarını API key ile doğrudan Workshop'a "
    "yükleyen bir endpoint sunmuyor. API key ile detay sorgulama/güncelleme "
    "yapılabilir; dosya bitleri Steamworks SDK, SteamCMD veya Steam Community "
    "web oturumu üzerinden gider."
)


TEMPLATE_SNIPPET_HINTS = {
    "uniform": "Atölye vitrini ayarları",
    "multi": "Çizim vitrini boyut hilesi",
    "single": "Ekran görüntüsü file_type",
}


# ==========================================================
#   PRESET JSON — Yükleme / Kaydetme
# ==========================================================

_PRESETS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "steam_splitter_presets.json")


_CONFIG_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "steam_splitter_config.json")


_PROFILES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "steam_splitter_profiles.json")

PROFILE_KEYS = (
    "border_fx_enabled", "border_fx_template", "border_fx_color",
    "border_fx_opacity", "border_fx_glow",
    "text_overlay_enabled", "text_overlay_text", "text_overlay_color",
    "text_overlay_size", "text_overlay_position", "text_overlay_opacity",
    "auto_enhance_enabled", "auto_enhance_intensity",
    "auto_upload", "steam_community_auto_submit",
)


_PROJECTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "steam_splitter_projects.json")


def load_custom_presets():
    """
    steam_splitter_presets.json içindeki özel şablonları TEMPLATES listesine ekler.
    Sadece 'uniform' modlu, henüz listede olmayan şablonlar eklenir.
    """
    if not os.path.exists(_PRESETS_FILE):
        return
    try:
        with open(_PRESETS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        existing_names = {t["name"] for t in TEMPLATES}
        for p in data:
            name = p.get("name", "")
            # JSON formatı: name, width, height, parts, last_byte, prefix
            # Zaten varsa atla
            if name in existing_names:
                continue
            tmpl = {
                "name": name,
                "mode": "uniform",
                "width": p.get("width", 750),
                "height": p.get("height", 1250),
                "parts": p.get("parts", 5),
                "patch": p.get("last_byte", 0) != 0,
                "prefix": p.get("prefix", "cus"),
            }
            TEMPLATES.append(tmpl)
            existing_names.add(name)
    except Exception as e:
        _log.error(f"[PRESETS LOAD ERR] {e}")


def save_custom_presets():
    """
    TEMPLATES listesinden 'cus' prefix'li (özel) şablonları JSON'a yazar.
    İlk 3 built-in şablon korunur, kaydedilmez.
    """
    try:
        custom = []
        for t in TEMPLATES:
            if t.get("prefix") not in ("work", "art", "shot"):
                entry = {
                    "name": t["name"],
                    "width": t.get("width", 750),
                    "height": t.get("height", 1250),
                    "parts": t.get("parts", 5),
                    "last_byte": 33 if t.get("patch") else 0,
                    "prefix": t.get("prefix", "cus"),
                }
                custom.append(entry)
        with open(_PRESETS_FILE, "w", encoding="utf-8") as f:
            json.dump(custom, f, ensure_ascii=False, indent=2)
    except Exception as e:
        _log.error(f"[PRESETS SAVE ERR] {e}")


def load_profiles() -> dict:
    """steam_splitter_profiles.json'u dict olarak döner (isim -> ayar seti)."""
    if not os.path.exists(_PROFILES_FILE):
        return {}
    try:
        with open(_PROFILES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        _log.error(f"[PROFILES LOAD ERR] {e}")
        return {}


def save_profiles(profiles: dict):
    try:
        with open(_PROFILES_FILE, "w", encoding="utf-8") as f:
            json.dump(profiles, f, ensure_ascii=False, indent=2)
    except Exception as e:
        _log.error(f"[PROFILES SAVE ERR] {e}")


def load_projects() -> dict:
    """steam_splitter_projects.json'u dict olarak döner (proje adı -> aktif iş
    durumu: giriş dosyaları/klasörü, şablon, çıktı klasörü, Workshop item bilgisi)."""
    if not os.path.exists(_PROJECTS_FILE):
        return {}
    try:
        with open(_PROJECTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        _log.error(f"[PROJECTS LOAD ERR] {e}")
        return {}


def save_projects(projects: dict):
    try:
        with open(_PROJECTS_FILE, "w", encoding="utf-8") as f:
            json.dump(projects, f, ensure_ascii=False, indent=2)
    except Exception as e:
        _log.error(f"[PROJECTS SAVE ERR] {e}")


def load_config() -> dict:
    """steam_splitter_config.json'u dict olarak döner."""
    defaults = {
        "default_preset": "Workshop 5-Parça (Otomatik Boyut)",
        "output_dir": "",
        "last_input_dir": "",
        "open_output_after_process": False,
        "auto_upload": False,
        "steam_api_key": "",
        "steam_app_id": "",
        "steam_published_file_id": "",
        "steam_community_upload_url": "https://steamcommunity.com/sharedfiles/edititem/767/3/",
        "steam_community_profile_dir": os.path.join(
            os.path.dirname(os.path.abspath(__file__)), ".steam_browser_profile"),
        "steam_community_auto_submit": False,
        "steam_community_wait_after_upload_ms": 1200,
        "steam_community_title_template": "\u200e ",
        "border_fx_enabled": False,
        "border_fx_template": "",
        "border_fx_color": "#8B5CF6",
        "border_fx_opacity": 100,
        "border_fx_glow": 35,
        "text_overlay_enabled": False,
        "text_overlay_text": "",
        "text_overlay_color": "#FFFFFF",
        "text_overlay_size": 6,
        "text_overlay_position": "Alt Orta",
        "text_overlay_opacity": 100,
        "auto_enhance_enabled": False,
        "auto_enhance_intensity": 50,
        "multi_band_count": 3,
        "output_format": "png",     # png | jpg (jpg'de patch uygulanmaz)
        "jpg_quality": 90,
        "gif_lossy": 80,
        "gif_colors": 128,
    }
    if not os.path.exists(_CONFIG_FILE):
        return defaults
    try:
        with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        defaults.update(data)
    except Exception as e:
        _log.error(f"[CONFIG LOAD ERR] {e}")
    return defaults


def save_config(cfg: dict):
    try:
        with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        _log.error(f"[CONFIG SAVE ERR] {e}")


def _masked_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "*" * (len(key) - 8) + key[-4:]


def steam_api_config_errors(cfg: dict) -> list[str]:
    errors = []
    if not cfg.get("steam_api_key", "").strip():
        errors.append("steam_api_key boş")
    if not cfg.get("steam_app_id", "").strip():
        errors.append("steam_app_id boş")
    if not cfg.get("steam_published_file_id", "").strip():
        errors.append("steam_published_file_id boş")
    return errors


def fetch_steam_published_file_details(published_file_id: str) -> dict:
    payload = urllib.parse.urlencode({
        "itemcount": 1,
        "publishedfileids[0]": published_file_id,
    }).encode("utf-8")
    req = urllib.request.Request(
        STEAM_PUBLISHED_FILE_DETAILS_URL,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    details = data.get("response", {}).get("publishedfiledetails", [])
    return details[0] if details else {}


def get_template_console_snippet(template: dict) -> tuple[str, str]:
    title = TEMPLATE_SNIPPET_HINTS.get(template.get("mode"), "")
    for snippet_title, snippet in STEAM_CONSOLE_SNIPPETS:
        if snippet_title == title:
            return snippet_title, snippet
    return "", ""


def build_steam_upload_manifest(file_paths: list[str], cfg: dict, outdir: str,
                                template: dict | None = None) -> str:
    os.makedirs(outdir, exist_ok=True)
    manifest_path = os.path.join(outdir, "steam_upload_manifest.json")
    files = []
    for path in file_paths:
        try:
            size = os.path.getsize(path)
        except Exception:
            size = 0
        files.append({
            "path": os.path.abspath(path),
            "name": os.path.basename(path),
            "size": size,
        })

    snippet_title, snippet = get_template_console_snippet(template or {})
    manifest = {
        "created_by": "Steam Splitter PRO",
        "direct_web_api_upload_supported": False,
        "note": STEAM_DIRECT_UPLOAD_NOTE,
        "steam": {
            "api_key": _masked_key(cfg.get("steam_api_key", "")),
            "app_id": cfg.get("steam_app_id", ""),
            "published_file_id": cfg.get("steam_published_file_id", ""),
        },
        "steam_community": {
            "url": cfg.get("steam_community_upload_url", "https://steamcommunity.com/sharedfiles/edititem/767/3/"),
            "profile_dir": cfg.get("steam_community_profile_dir", ""),
            "auto_submit": bool(cfg.get("steam_community_auto_submit", False)),
            "wait_after_upload_ms": int(cfg.get("steam_community_wait_after_upload_ms", 1200) or 1200),
            "title_template": cfg.get("steam_community_title_template", "\u200e "),
            "console_snippet_title": snippet_title,
            "console_snippet": snippet,
        },
        "files": files,
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return manifest_path


def upload_status_path(manifest_path: str) -> str:
    return os.path.splitext(manifest_path)[0] + ".status.json"


# Uygulama başlarken özel presetleri yükle
load_custom_presets()
