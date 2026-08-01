import os

from ohwang.cli import _load_env


def test_load_env_from_workdir(tmp_path):
    (tmp_path / ".env").write_text(
        "FOO=bar\n# comment\nEMPTY=\nQUOTED='single'\nDQUOTED=\"double\"\n",
        encoding="utf-8",
    )
    _load_env(str(tmp_path))
    assert os.environ.get("FOO") == "bar"
    assert os.environ.get("EMPTY") == ""
    assert os.environ.get("QUOTED") == "single"
    assert os.environ.get("DQUOTED") == "double"


def test_load_env_does_not_override_existing(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text("EXISTING_KEY=newvalue\n", encoding="utf-8")
    monkeypatch.setenv("EXISTING_KEY", "keepme")
    _load_env(str(tmp_path))
    assert os.environ["EXISTING_KEY"] == "keepme"


def test_load_env_missing_file(tmp_path):
    _load_env(str(tmp_path))
    assert os.environ.get("SHOULD_NOT_EXIST_XYZ") is None
