import json
import os

import pytest

import config


@pytest.fixture(autouse=True)
def isolated_files(tmp_path, monkeypatch):
    """Her testte gerçek steam_splitter_*.json dosyalarına dokunmasın diye
    config modülünün dosya yollarını tmp_path'e yönlendir."""
    monkeypatch.setattr(config, "_CONFIG_FILE", str(tmp_path / "cfg.json"))
    monkeypatch.setattr(config, "_PRESETS_FILE", str(tmp_path / "presets.json"))
    yield


# ── load_config / save_config ─────────────────────────────

def test_load_config_defaults_when_file_missing():
    cfg = config.load_config()
    assert cfg["default_preset"]
    assert cfg["steam_community_auto_submit"] is False
    assert cfg["output_dir"] == ""


def test_save_then_load_config_roundtrip():
    cfg = config.load_config()
    cfg["steam_api_key"] = "abc123"
    cfg["border_fx_opacity"] = 42
    config.save_config(cfg)

    reloaded = config.load_config()
    assert reloaded["steam_api_key"] == "abc123"
    assert reloaded["border_fx_opacity"] == 42


def test_load_config_merges_partial_file_with_defaults(tmp_path):
    with open(config._CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"steam_api_key": "only-this-key"}, f)
    cfg = config.load_config()
    assert cfg["steam_api_key"] == "only-this-key"
    assert "default_preset" in cfg  # varsayılanlarla birleşti


def test_load_config_survives_corrupt_json():
    with open(config._CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write("{not valid json")
    cfg = config.load_config()
    assert cfg["output_dir"] == ""  # varsayılana düştü, patlamadı


# ── _masked_key ────────────────────────────────────────────

def test_masked_key_empty():
    assert config._masked_key("") == ""


def test_masked_key_short_fully_masked():
    assert config._masked_key("abcd") == "****"


def test_masked_key_long_shows_head_and_tail():
    masked = config._masked_key("ABCD1234EFGH")
    assert masked.startswith("ABCD")
    assert masked.endswith("EFGH")
    assert "*" in masked


# ── steam_api_config_errors ────────────────────────────────

def test_steam_api_config_errors_all_missing():
    errors = config.steam_api_config_errors({})
    assert len(errors) == 3


def test_steam_api_config_errors_none_when_filled():
    cfg = {"steam_api_key": "k", "steam_app_id": "1", "steam_published_file_id": "2"}
    assert config.steam_api_config_errors(cfg) == []


# ── custom presets ─────────────────────────────────────────

def test_load_custom_presets_skips_existing_names():
    existing_names = {t["name"] for t in config.TEMPLATES}
    before = len(config.TEMPLATES)
    with open(config._PRESETS_FILE, "w", encoding="utf-8") as f:
        json.dump([{"name": next(iter(existing_names)), "width": 999, "parts": 9}], f)
    config.load_custom_presets()
    assert len(config.TEMPLATES) == before  # zaten var olan isim tekrar eklenmedi


def test_load_and_save_custom_preset_roundtrip():
    before = len(config.TEMPLATES)
    unique_name = "TestPreset__pytest_only"
    with open(config._PRESETS_FILE, "w", encoding="utf-8") as f:
        json.dump([{"name": unique_name, "width": 300, "height": 400,
                    "parts": 3, "last_byte": 33, "prefix": "cus"}], f)
    try:
        config.load_custom_presets()
        added = [t for t in config.TEMPLATES if t["name"] == unique_name]
        assert len(added) == 1
        assert added[0]["patch"] is True
        assert added[0]["mode"] == "uniform"

        config.save_custom_presets()
        with open(config._PRESETS_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        names = [p["name"] for p in saved]
        assert unique_name in names
        assert not any(p["prefix"] in ("work", "art", "shot") for p in saved)
    finally:
        config.TEMPLATES[:] = [t for t in config.TEMPLATES if t["name"] != unique_name]
    assert len(config.TEMPLATES) == before


# ── manifest / snippet yardımcıları ────────────────────────

def test_get_template_console_snippet_uniform():
    title, snippet = config.get_template_console_snippet({"mode": "uniform"})
    assert title == "Atölye vitrini ayarları"
    assert "consumer_app_id" in snippet


def test_get_template_console_snippet_unknown_mode_returns_empty():
    title, snippet = config.get_template_console_snippet({"mode": "does-not-exist"})
    assert title == ""
    assert snippet == ""


def test_build_steam_upload_manifest_structure(tmp_path):
    file1 = tmp_path / "a.png"
    file1.write_bytes(b"fake-png-bytes")
    cfg = config.load_config()
    cfg["steam_api_key"] = "supersecretkey123"

    manifest_path = config.build_steam_upload_manifest(
        [str(file1)], cfg, str(tmp_path), {"mode": "uniform"})

    assert os.path.exists(manifest_path)
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["files"][0]["name"] == "a.png"
    assert manifest["files"][0]["size"] == len(b"fake-png-bytes")
    # API key manifestte asla düz metin olarak durmamalı
    assert manifest["steam"]["api_key"] != "supersecretkey123"
    assert manifest["steam_community"]["console_snippet_title"] == "Atölye vitrini ayarları"


def test_upload_status_path_derives_from_manifest_path():
    assert config.upload_status_path("/tmp/foo/steam_upload_manifest.json") == \
        "/tmp/foo/steam_upload_manifest.status.json"
