import os
import tempfile

from ohwang.flags import FeatureFlags


def test_flags_default_values():
    d = tempfile.mkdtemp()
    flags = FeatureFlags(d)
    assert flags.is_enabled("web_fetch") is True
    assert flags.is_enabled("web_search") is True
    assert flags.is_enabled("todo") is True
    assert flags.is_enabled("lsp") is False
    assert flags.is_enabled("plugin") is False
    assert flags.is_enabled("coordinator") is False


def test_flags_env_override():
    d = tempfile.mkdtemp()
    os.environ["OHWANG_FEATURE_LSP"] = "1"
    try:
        flags = FeatureFlags(d)
        assert flags.is_enabled("lsp") is True
    finally:
        del os.environ["OHWANG_FEATURE_LSP"]


def test_flags_env_override_disable():
    d = tempfile.mkdtemp()
    os.environ["OHWANG_FEATURE_WEB_FETCH"] = "0"
    try:
        flags = FeatureFlags(d)
        assert flags.is_enabled("web_fetch") is False
    finally:
        del os.environ["OHWANG_FEATURE_WEB_FETCH"]


def test_flags_file_override():
    d = tempfile.mkdtemp()
    flags_dir = os.path.join(d, ".ohwang")
    os.makedirs(flags_dir, exist_ok=True)
    import json
    with open(os.path.join(flags_dir, "flags.json"), "w") as f:
        json.dump({"features": {"lsp": True, "web_search": False}}, f)

    flags = FeatureFlags(d)
    assert flags.is_enabled("lsp") is True
    assert flags.is_enabled("web_search") is False


def test_flags_enable_disable():
    d = tempfile.mkdtemp()
    flags = FeatureFlags(d)
    flags.enable("lsp")
    assert flags.is_enabled("lsp") is True
    flags.disable("lsp")
    assert flags.is_enabled("lsp") is False


def test_flags_list_all():
    d = tempfile.mkdtemp()
    flags = FeatureFlags(d)
    all_flags = flags.list_all()
    assert isinstance(all_flags, dict)
    assert "web_fetch" in all_flags
    assert "todo" in all_flags


def test_flags_unknown_default_false():
    d = tempfile.mkdtemp()
    flags = FeatureFlags(d)
    assert flags.is_enabled("totally_unknown_feature") is False
