import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def test_tui_widget_no_undefined_chat_refs():
    src = (_ROOT / "ohwang/tui/widgets/app.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    defined = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
            defined.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            defined.add(node.id)

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id == "ChatLog":
                raise AssertionError(
                    "tui app.py references undefined ChatLog (class is ChatPanel)"
                )

    assert "ChatPanel" in defined
