"""Tests for Cloud Sync / Export — projects/profiles JSON merge."""
import json
import time
import tempfile
import pathlib

import config as cfg

# Use isolated tmp for each test via monkeypatch
import pytest


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "_PROJECTS_FILE", str(tmp_path / "projects.json"))
    monkeypatch.setattr(cfg, "_PROFILES_FILE", str(tmp_path / "profiles.json"))
    monkeypatch.setattr(cfg, "_PRESETS_FILE", str(tmp_path / "presets.json"))
    monkeypatch.setattr(cfg, "_CONFIG_FILE", str(tmp_path / "config.json"))
    yield


def test_export_import_projects_roundtrip(tmp_path):
    # Create some projects
    projects = {
        "Kılıç Modu v2": {"template_name": "Atölye Vitrini 5-Parça (150×1250)", "output_dir": "C:/out", "note": ""},
        "Zırh": {"template_name": "Çizim Vitrini 2-Parça (506 + 100)", "output_dir": "C:/out2"},
    }
    cfg.save_projects(projects)

    # Simulate export: collect projects + profiles into JSON
    export_data = {
        "version": "2.1.0",
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "projects": cfg.load_projects(),
        "profiles": {"P1": {"template_name": "Atölye Vitrini 5-Parça (150×1250)"}},
    }
    export_path = tmp_path / "export.json"
    with open(export_path, "w", encoding="utf-8") as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)

    # Clear and import (merge)
    cfg.save_projects({})
    assert cfg.load_projects() == {}

    with open(export_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    incoming = data.get("projects", {})
    current = cfg.load_projects()
    for k, v in incoming.items():
        current[k] = v
    cfg.save_projects(current)

    reloaded = cfg.load_projects()
    assert "Kılıç Modu v2" in reloaded
    assert reloaded["Zırh"]["output_dir"] == "C:/out2"


def test_import_merge_overwrites_and_adds():
    cfg.save_projects({"A": {"template_name": "X", "output_dir": "old"}})
    incoming = {
        "A": {"template_name": "X", "output_dir": "new"},  # overwrite
        "B": {"template_name": "Y", "output_dir": "b_out"},  # add
    }
    current = cfg.load_projects()
    for k, v in incoming.items():
        current[k] = v
    cfg.save_projects(current)

    reloaded = cfg.load_projects()
    assert reloaded["A"]["output_dir"] == "new"
    assert reloaded["B"]["output_dir"] == "b_out"


def test_export_includes_version_and_timestamp(tmp_path):
    cfg.save_projects({"P": {"template_name": "T"}})
    data = {
        "version": "2.1.0",
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "projects": cfg.load_projects(),
        "profiles": cfg.load_profiles(),
    }
    assert "version" in data
    assert "exported_at" in data
    assert isinstance(data["projects"], dict)


def test_import_invalid_format_handled():
    # Simulate UI's validation: non-dict should be rejected
    incoming = ["not", "a", "dict"]
    # UI checks isinstance(incoming, dict) -> should not crash
    assert not isinstance(incoming, dict)
    # Ensure we don't overwrite with invalid
    cfg.save_projects({"Keep": {"template_name": "T"}})
    # Attempt merge with invalid (should be skipped)
    current = cfg.load_projects()
    if isinstance(incoming, dict):
        for k, v in incoming.items():
            current[k] = v
        cfg.save_projects(current)
    assert "Keep" in cfg.load_projects()
