from ohwang.tools.file_read import FileReadTool
from ohwang.tools.file_write import FileWriteTool
from ohwang.tools.file_edit import FileEditTool
from ohwang.tools.glob import GlobTool
from ohwang.tools.grep import GrepTool


def test_file_write_creates_nested_dirs(tmp_path):
    p = tmp_path / "a" / "b" / "notes.txt"
    r = FileWriteTool().execute({"file_path": str(p), "content": "hello"})
    assert not r.is_error
    assert "Created" in r.content
    assert p.read_text(encoding="utf-8") == "hello"


def test_file_write_overwrites(tmp_path):
    p = tmp_path / "f.txt"
    p.write_text("old", encoding="utf-8")
    r = FileWriteTool().execute({"file_path": str(p), "content": "new"})
    assert "Overwrote" in r.content
    assert p.read_text(encoding="utf-8") == "new"


def test_file_read_lines_numbered(tmp_path):
    p = tmp_path / "f.txt"
    p.write_text("l1\nl2\nl3\n", encoding="utf-8")
    r = FileReadTool().execute({"file_path": str(p)})
    assert not r.is_error
    assert "1: l1" in r.content
    assert "3: l3" in r.content


def test_file_read_offset_limit(tmp_path):
    p = tmp_path / "f.txt"
    p.write_text("l1\nl2\nl3\nl4\n", encoding="utf-8")
    r = FileReadTool().execute({"file_path": str(p), "offset": 2, "limit": 2})
    assert "2: l2" in r.content
    assert "3: l3" in r.content
    assert "1: l1" not in r.content


def test_file_read_empty(tmp_path):
    p = tmp_path / "empty.txt"
    p.write_text("", encoding="utf-8")
    r = FileReadTool().execute({"file_path": str(p)})
    assert "(empty file)" in r.content


def test_file_read_missing(tmp_path):
    r = FileReadTool().execute({"file_path": str(tmp_path / "nope.txt")})
    assert r.is_error
    assert "not found" in r.content


def test_file_edit_single(tmp_path):
    p = tmp_path / "f.txt"
    p.write_text("apple banana", encoding="utf-8")
    r = FileEditTool().execute(
        {"file_path": str(p), "old_string": "apple", "new_string": "orange"}
    )
    assert not r.is_error
    assert "Replaced 1" in r.content
    assert p.read_text(encoding="utf-8") == "orange banana"


def test_file_edit_replace_all(tmp_path):
    p = tmp_path / "f.txt"
    p.write_text("apple apple", encoding="utf-8")
    r = FileEditTool().execute(
        {"file_path": str(p), "old_string": "apple", "new_string": "pear", "replace_all": True}
    )
    assert not r.is_error
    assert "Replaced 2" in r.content
    assert p.read_text(encoding="utf-8") == "pear pear"


def test_file_edit_not_found(tmp_path):
    p = tmp_path / "f.txt"
    p.write_text("abc", encoding="utf-8")
    r = FileEditTool().execute(
        {"file_path": str(p), "old_string": "zzz", "new_string": "x"}
    )
    assert r.is_error
    assert "not found" in r.content


def test_file_edit_ambiguous_without_replace_all(tmp_path):
    p = tmp_path / "f.txt"
    p.write_text("x y x", encoding="utf-8")
    r = FileEditTool().execute({"file_path": str(p), "old_string": "x", "new_string": "q"})
    assert r.is_error
    assert "replace_all" in r.content


def test_file_edit_empty_old_string(tmp_path):
    p = tmp_path / "f.txt"
    p.write_text("abc", encoding="utf-8")
    r = FileEditTool().execute({"file_path": str(p), "old_string": "", "new_string": "x"})
    assert r.is_error


def test_file_edit_missing_file(tmp_path):
    r = FileEditTool().execute(
        {"file_path": str(tmp_path / "nope.txt"), "old_string": "a", "new_string": "b"}
    )
    assert r.is_error


def test_glob_recursive(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "b.py").write_text("", encoding="utf-8")
    (tmp_path / "b.py").write_text("", encoding="utf-8")
    (tmp_path / "c.txt").write_text("", encoding="utf-8")
    r = GlobTool().execute({"pattern": "**/*.py", "path": str(tmp_path)})
    assert not r.is_error
    assert "a/b.py" in r.content
    assert "b.py" in r.content
    assert "c.txt" not in r.content


def test_glob_no_match(tmp_path):
    r = GlobTool().execute({"pattern": "**/*.rs", "path": str(tmp_path)})
    assert "No files matched" in r.content


def test_glob_bad_dir():
    r = GlobTool().execute({"pattern": "**/*.py", "path": "Z:/definitely/not/here"})
    assert r.is_error


def test_grep_finds_matches(tmp_path):
    (tmp_path / "a.txt").write_text("hello world\nbye\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("nothing\n", encoding="utf-8")
    r = GrepTool().execute({"pattern": "hello", "path": str(tmp_path)})
    assert not r.is_error
    assert "a.txt:1:hello world" in r.content


def test_grep_no_match(tmp_path):
    (tmp_path / "a.txt").write_text("zzz", encoding="utf-8")
    r = GrepTool().execute({"pattern": "nope", "path": str(tmp_path)})
    assert "No matches" in r.content


def test_grep_invalid_regex(tmp_path):
    r = GrepTool().execute({"pattern": "(", "path": str(tmp_path)})
    assert r.is_error
    assert "Invalid regex" in r.content


def test_grep_single_file(tmp_path):
    p = tmp_path / "solo.txt"
    p.write_text("needle here\n", encoding="utf-8")
    r = GrepTool().execute({"pattern": "needle", "path": str(p)})
    assert "solo.txt:1:needle here" in r.content


def test_grep_include_filter(tmp_path):
    (tmp_path / "a.py").write_text("match\n", encoding="utf-8")
    (tmp_path / "a.md").write_text("match\n", encoding="utf-8")
    r = GrepTool().execute({"pattern": "match", "path": str(tmp_path), "include": "*.py"})
    assert "a.py" in r.content
    assert "a.md" not in r.content


def test_grep_skips_ignored_dirs(tmp_path):
    ignored = tmp_path / "__pycache__"
    ignored.mkdir()
    (ignored / "c.py").write_text("match\n", encoding="utf-8")
    (tmp_path / "d.py").write_text("match\n", encoding="utf-8")
    r = GrepTool().execute({"pattern": "match", "path": str(tmp_path)})
    assert "d.py" in r.content
    assert "__pycache__" not in r.content
