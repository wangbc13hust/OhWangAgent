from ohwang.tools.todo import TodoStore, TodoWriteTool


def test_store_render_empty():
    s = TodoStore()
    assert s.render() == ""


def test_tool_updates_and_renders():
    s = TodoStore()
    t = TodoWriteTool(s)
    r = t.execute(
        {"todos": [{"content": "write tests", "status": "in_progress", "priority": "high"}]}
    )
    assert not r.is_error
    assert len(s.todos) == 1
    assert s.todos[0]["content"] == "write tests"
    rendered = s.render()
    assert "[*]" in rendered
    assert "write tests" in rendered
    assert "high" in rendered


def test_tool_clears():
    s = TodoStore()
    t = TodoWriteTool(s)
    t.execute({"todos": [{"content": "a", "status": "pending", "priority": "medium"}]})
    r = t.execute({"todos": []})
    assert s.todos == []
    assert "cleared" in r.content.lower()


def test_todo_injected_into_system_context():
    from tests.helpers import build_agent

    agent, provider = build_agent(
        [[{"type": "text", "text": "done"}]], with_todo=True
    )
    agent.todo_store.set(
        [{"content": "my task", "status": "in_progress", "priority": "high"}]
    )
    agent.run("go")
    assert "Current Todo List" in provider.calls[0]["system"]
    assert "my task" in provider.calls[0]["system"]
