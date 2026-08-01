from ohwang.tools.multi_edit import MultiEditTool


def test_multi_edit_preview_no_write(tmp_path):
    p1 = tmp_path / "a.txt"
    p2 = tmp_path / "b.txt"
    p1.write_text("alpha beta", encoding="utf-8")
    p2.write_text("gamma beta", encoding="utf-8")
    tool = MultiEditTool()
    r = tool.execute(
        {
            "edits": [
                {"file_path": str(p1), "old_string": "beta", "new_string": "omega"},
                {"file_path": str(p2), "old_string": "beta", "new_string": "omega"},
            ]
        }
    )
    assert not r.is_error
    assert "PREVIEW" in r.content
    assert p1.read_text(encoding="utf-8") == "alpha beta"
    assert p2.read_text(encoding="utf-8") == "gamma beta"


def test_multi_edit_apply(tmp_path):
    p1 = tmp_path / "a.txt"
    p1.write_text("alpha beta", encoding="utf-8")
    tool = MultiEditTool()
    r = tool.execute(
        {
            "edits": [{"file_path": str(p1), "old_string": "beta", "new_string": "omega"}],
            "apply": True,
        }
    )
    assert not r.is_error
    assert "OK" in r.content
    assert p1.read_text(encoding="utf-8") == "alpha omega"


def test_multi_edit_skips_missing_and_unmatched(tmp_path):
    tool = MultiEditTool()
    r = tool.execute(
        {
            "edits": [
                {"file_path": "nope.txt", "old_string": "x", "new_string": "y"},
                {"file_path": "nope2.txt", "old_string": "z", "new_string": "w"},
            ],
            "apply": True,
        }
    )
    assert r.is_error
    assert "file not found" in r.content


def test_multi_edit_replace_all(tmp_path):
    p = tmp_path / "c.txt"
    p.write_text("x x x", encoding="utf-8")
    tool = MultiEditTool()
    r = tool.execute(
        {
            "edits": [
                {"file_path": str(p), "old_string": "x", "new_string": "y", "replace_all": True}
            ],
            "apply": True,
        }
    )
    assert not r.is_error
    assert p.read_text(encoding="utf-8") == "y y y"


def test_multi_edit_ambiguous_without_replace_all(tmp_path):
    p = tmp_path / "d.txt"
    p.write_text("x x", encoding="utf-8")
    tool = MultiEditTool()
    r = tool.execute(
        {
            "edits": [{"file_path": str(p), "old_string": "x", "new_string": "y"}],
            "apply": True,
        }
    )
    assert r.is_error
    assert "replace_all" in r.content


def test_multi_edit_empty_edits():
    tool = MultiEditTool()
    r = tool.execute({"edits": []})
    assert r.is_error
    assert "No edits" in r.content
