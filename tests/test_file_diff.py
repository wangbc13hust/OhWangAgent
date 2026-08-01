from ohwang.tools.file_diff import FileDiffTool, FilePreviewEditTool, make_unified_diff


def test_make_unified_diff_shows_change():
    diff = make_unified_diff("line one\nline two\n", "line one\nline TWO\n", "f.txt")
    assert "-line two" in diff
    assert "+line TWO" in diff


def test_make_unified_diff_identical():
    assert make_unified_diff("same\n", "same\n", "f") == ""


def test_file_diff_tool_preview(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("hello\nworld\n", encoding="utf-8")
    tool = FileDiffTool()
    r = tool.execute({"file_path": str(p), "new_content": "hello\nuniverse\n"})
    assert not r.is_error
    assert "-world" in r.content
    assert "+universe" in r.content
    assert p.read_text(encoding="utf-8") == "hello\nworld\n"


def test_file_diff_tool_missing():
    tool = FileDiffTool()
    r = tool.execute({"file_path": "nope.txt", "new_content": "x"})
    assert r.is_error


def test_preview_edit_no_write_by_default(tmp_path):
    p = tmp_path / "b.txt"
    p.write_text("old", encoding="utf-8")
    tool = FilePreviewEditTool()
    r = tool.execute({"file_path": str(p), "new_content": "new"})
    assert "Preview" in r.content
    assert p.read_text(encoding="utf-8") == "old"


def test_preview_edit_apply(tmp_path):
    p = tmp_path / "c.txt"
    p.write_text("old", encoding="utf-8")
    tool = FilePreviewEditTool()
    r = tool.execute({"file_path": str(p), "new_content": "new", "apply": True})
    assert "Applied edit" in r.content
    assert p.read_text(encoding="utf-8") == "new"


def test_preview_edit_identical():
    from tempfile import NamedTemporaryFile
    import os

    with NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("same")
        path = f.name
    try:
        tool = FilePreviewEditTool()
        r = tool.execute({"file_path": path, "new_content": "same"})
        assert "No differences" in r.content
    finally:
        os.unlink(path)
