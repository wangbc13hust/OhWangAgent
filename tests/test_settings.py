import os
import tempfile

from ohwang.services.settings import load_settings


def test_load_settings_missing_file():
    d = tempfile.mkdtemp()
    result = load_settings(d)
    assert result == {"allow": [], "ask": [], "deny": []}


def test_load_settings_with_file():
    d = tempfile.mkdtemp()
    ohwang_dir = os.path.join(d, ".ohwang")
    os.makedirs(ohwang_dir, exist_ok=True)
    import json
    with open(os.path.join(ohwang_dir, "settings.json"), "w") as f:
        json.dump({
            "permissions": {
                "allow": ["file_read", "grep"],
                "ask": ["bash"],
                "deny": ["file_write"],
            }
        }, f)
    result = load_settings(d)
    assert "file_read" in result["allow"]
    assert "bash" in result["ask"]
    assert "file_write" in result["deny"]


def test_load_settings_invalid_json():
    d = tempfile.mkdtemp()
    ohwang_dir = os.path.join(d, ".ohwang")
    os.makedirs(ohwang_dir, exist_ok=True)
    with open(os.path.join(ohwang_dir, "settings.json"), "w") as f:
        f.write("not json")
    result = load_settings(d)
    assert result == {"allow": [], "ask": [], "deny": []}


def test_load_settings_partial():
    d = tempfile.mkdtemp()
    ohwang_dir = os.path.join(d, ".ohwang")
    os.makedirs(ohwang_dir, exist_ok=True)
    import json
    with open(os.path.join(ohwang_dir, "settings.json"), "w") as f:
        json.dump({"permissions": {"allow": ["grep"]}}, f)
    result = load_settings(d)
    assert result["allow"] == ["grep"]
    assert result["ask"] == []
    assert result["deny"] == []
