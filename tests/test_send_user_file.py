from ohwang.tools.send_user_file import SendUserFileTool


def test_send_user_file_shows_file(tmp_path, capsys):
    p = tmp_path / "report.md"
    p.write_text("line1\nline2\nline3", encoding="utf-8")
    seen = []
    tool = SendUserFileTool(display=lambda text: seen.append(text))
    r = tool.execute({"file_path": str(p), "summary": "a report"})
    assert not r.is_error
    assert "report.md" in r.content
    assert "a report" in r.content
    assert any("line1" in s for s in seen)
    assert any("report.md" in s for s in seen)


def test_send_user_file_truncates_large(tmp_path):
    p = tmp_path / "big.txt"
    p.write_text("x" * 5000, encoding="utf-8")
    seen = []
    tool = SendUserFileTool(display=lambda text: seen.append(text))
    r = tool.execute({"file_path": str(p), "summary": "big file"})
    assert not r.is_error
    assert any("truncated" in s for s in seen)


def test_send_user_file_missing(tmp_path):
    tool = SendUserFileTool()
    r = tool.execute({"file_path": str(tmp_path / "nope.txt"), "summary": "x"})
    assert r.is_error
    assert "File not found" in r.content


def test_send_user_file_bom(tmp_path):
    p = tmp_path / "bom.txt"
    p.write_bytes(b"\xef\xbb\xbfhello world")
    seen = []
    tool = SendUserFileTool(display=lambda text: seen.append(text))
    r = tool.execute({"file_path": str(p), "summary": "bom file"})
    assert not r.is_error
    assert any("hello world" in s for s in seen)
