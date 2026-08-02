import os

from ohwang.cli import _load_env, _suggest_prompts


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


def test_load_env_strips_only_a_matching_outer_pair(tmp_path):
    # old code did .strip("'").strip('"') which peeled EVERY surrounding quote,
    # mangling values like "\"''nested''\"" down to "nested".
    (tmp_path / ".env").write_text("VAL=\"''nested''\"\n", encoding="utf-8")
    _load_env(str(tmp_path))
    assert os.environ.get("VAL") == "''nested''"


def _fake_agent(todos=None, facts=None, iterations=0):
    from ohwang.agent import Agent
    from ohwang.config import Config
    from ohwang.modes import Mode
    from ohwang.permissions import PermissionManager
    from ohwang.services.memory import MemoryStore
    from ohwang.tools.registry import ToolRegistry
    from ohwang.tools.todo import TodoStore
    from ohwang.tools.base import BaseTool, ToolResult

    class T(BaseTool):
        name = "t"
        description = "d"
        input_schema = {}

        def execute(self, input):
            return ToolResult(content="ok")

    agent = Agent(
        provider=None,
        tools=ToolRegistry().register(T()),
        permissions=PermissionManager(mode=Mode.AUTO),
        config=Config(workdir=os.getcwd()).resolve(),
        system="sys",
    )
    agent.iterations = iterations
    if todos is not None:
        agent.todo_store = TodoStore()
        agent.todo_store.set(todos)
    if facts is not None:
        agent.memory_store = MemoryStore(os.path.join(os.getcwd(), ".ohwang"))
        agent.memory_store._facts_cache = {k: {"value": v, "tags": []} for k, v in facts.items()}
        agent.memory_store._facts_mtime = 1
    return agent


def test_suggest_prompts_empty_workdir(tmp_path):
    agent = _fake_agent()
    suggestions = _suggest_prompts(str(tmp_path), agent)
    assert isinstance(suggestions, list)
    assert 1 <= len(suggestions) <= 3
    assert suggestions


def test_suggest_prompts_with_files(tmp_path):
    (tmp_path / "meeting.md").write_text("notes", encoding="utf-8")
    agent = _fake_agent()
    suggestions = _suggest_prompts(str(tmp_path), agent)
    assert any("meeting.md" in s for s in suggestions)


def test_suggest_prompts_with_todos(tmp_path):
    agent = _fake_agent(todos=[{"content": "写周报", "status": "pending", "priority": "high"}])
    suggestions = _suggest_prompts(str(tmp_path), agent)
    assert any("待办" in s for s in suggestions)


def test_build_agent_scheduler_runner_uses_shared_run_lock(monkeypatch, tmp_path):
    """The cron scheduler runner and the REPL must share ONE lock so they can
    never run the same Agent concurrently."""
    import argparse
    import ohwang.cli as cli
    from ohwang.providers.base import BaseProvider

    monkeypatch.chdir(tmp_path)

    class DummyProvider(BaseProvider):
        name = "dummy"

        def chat(self, system, messages, tools, max_tokens):
            yield from ()

    monkeypatch.setattr(cli, "create_provider", lambda *a, **k: DummyProvider("k", "m"))
    monkeypatch.setattr(
        cli.Agent, "run", lambda self, user_input, **kw: "done"
    )

    args = argparse.Namespace(
        provider="deepseek",
        model="m",
        api_key="k",
        base_url=None,
        max_tokens=100,
        auto_approve=False,
        plan=False,
        compact_threshold=100_000,
        workdir=None,
        no_mcp=True,
        no_proactive=True,
    )

    entered: list = []

    class TrackLock:
        def __enter__(self):
            entered.append(self)
            return self

        def __exit__(self, *a):
            return None

    lock = TrackLock()
    (
        _agent,
        _renderer,
        _config,
        _sessions,
        scheduler,
        _memext,
        _skill,
        _flags,
        _summarizer,
    ) = cli.build_agent(args, lock)

    assert scheduler._runner is not None
    assert scheduler._runner("hello") == "done"
    assert entered, "scheduler runner must acquire the run lock"
    assert entered[0] is lock, "scheduler runner must acquire the SAME lock the REPL uses"


def test_build_agent_assembly_smoke_with_cron_background_fire(monkeypatch, tmp_path):
    """Full assembly with the proactive scheduler started during build, then a
    real background cron fire must run the shared-lock runner without raising.

    Regression for the fragile closure ordering in build_agent
    (docs/PROJECT_REVIEW.md §3.1/§4): reordering the agent construction relative
    to scheduler.start() must not silently break background cron jobs.
    """
    import argparse
    import threading
    import time

    import ohwang.cli as cli
    from ohwang.providers.base import BaseProvider

    monkeypatch.chdir(tmp_path)

    class DummyProvider(BaseProvider):
        name = "dummy"

        def chat(self, system, messages, tools, max_tokens):
            yield from ()

    monkeypatch.setattr(cli, "create_provider", lambda *a, **k: DummyProvider("k", "m"))

    run_calls: list[str] = []
    monkeypatch.setattr(
        cli.Agent,
        "run",
        lambda self, user_input, **kw: run_calls.append(user_input) or "done",
    )

    args = argparse.Namespace(
        provider="deepseek",
        model="m",
        api_key="k",
        base_url=None,
        max_tokens=100,
        auto_approve=False,
        plan=False,
        compact_threshold=100_000,
        workdir=None,
        no_mcp=True,
        no_proactive=False,  # scheduler thread starts during assembly
    )
    (agent, _renderer, _config, _sessions, scheduler, _ext, _skills, _flags, _summarizer) = (
        cli.build_agent(args, threading.Lock())
    )

    # Assembly completed with the scheduler already running — the runner must be
    # wired so a background fire resolves the fully-constructed agent.
    assert scheduler._runner is not None

    # '* * * * *' matches any minute, so the next 1s poll fires it determinis-
    # tically (no minute-boundary race like a current-time expression).
    assert scheduler.add("smoke", "* * * * *", "hello")
    deadline = time.time() + 6
    while time.time() < deadline and not run_calls:
        time.sleep(0.2)
    scheduler.stop()
    assert run_calls == ["hello"], "background cron job must invoke the agent run"


def test_cmd_save_stores_summary(tmp_path):
    import ohwang.cli as cli
    from ohwang.services.session import SessionStore

    class FakeSummarizer:
        def summarize(self, provider, messages):
            return "- summary text"

    agent = _fake_agent()
    agent.messages = [{"role": "user", "content": [{"type": "text", "text": "hello"}]}]
    session_store = SessionStore(str(tmp_path))

    class R:
        def __init__(self):
            self.infos = []
            self.warns = []

        def info(self, m):
            self.infos.append(m)

        def warn(self, m):
            self.warns.append(m)

    cli._cmd_save(agent, R(), session_store, FakeSummarizer())
    items = session_store.list()
    assert len(items) == 1
    assert items[0]["summary"] == "- summary text"


def test_cmd_save_no_summarizer_still_saves(tmp_path):
    import ohwang.cli as cli
    from ohwang.services.session import SessionStore

    agent = _fake_agent()
    agent.messages = [{"role": "user", "content": [{"type": "text", "text": "hi"}]}]
    session_store = SessionStore(str(tmp_path))

    class R:
        def __init__(self):
            self.infos = []
            self.warns = []

        def info(self, m):
            self.infos.append(m)

        def warn(self, m):
            self.warns.append(m)

    cli._cmd_save(agent, R(), session_store, None)
    items = session_store.list()
    assert len(items) == 1
    assert items[0]["summary"] == ""


def test_cmd_resume_injects_summary(tmp_path):
    import ohwang.cli as cli
    from ohwang.services.session import SessionStore

    session_store = SessionStore(str(tmp_path))
    msgs = [{"role": "user", "content": [{"type": "text", "text": "hi"}]}]
    sid = session_store.save(msgs, preview="hi", summary="- brief")
    agent = _fake_agent()

    class R:
        class console:
            @staticmethod
            def input(prompt):
                return "1"

        def __init__(self):
            self.infos = []
            self.warns = []

        def info(self, m):
            self.infos.append(m)

        def warn(self, m):
            self.warns.append(m)

    cli._cmd_resume(agent, R(), session_store)
    assert agent.messages == msgs
    assert agent.session_summary == "- brief"


def test_sub_agent_has_own_permissions_and_inherits_policy(monkeypatch, tmp_path):
    import argparse
    from threading import Lock

    import ohwang.cli as cli
    from ohwang.modes import Mode
    from ohwang.permissions import PermissionManager
    from ohwang.providers.base import BaseProvider

    monkeypatch.chdir(tmp_path)

    class DummyProvider(BaseProvider):
        name = "dummy"

        def chat(self, system, messages, tools, max_tokens):
            yield from ()

    monkeypatch.setattr(cli, "create_provider", lambda *a, **k: DummyProvider("k", "m"))

    captured = {}
    real_dt = cli.default_tools

    def spy_dt(**kw):
        captured.update(kw)
        return real_dt(**kw)

    monkeypatch.setattr(cli, "default_tools", spy_dt)

    args = argparse.Namespace(
        provider="deepseek",
        model="m",
        api_key="k",
        base_url=None,
        max_tokens=100,
        auto_approve=False,
        plan=False,
        compact_threshold=100_000,
        workdir=None,
        no_mcp=True,
        no_proactive=True,
    )
    agent, *_ = cli.build_agent(args, Lock())

    factory = captured["agent_factory"]
    sub = factory()

    assert isinstance(sub.permissions, PermissionManager)
    assert sub.permissions is not agent.permissions  # its own manager, not the main one
    assert sub.permissions.mode is Mode.AUTO
    # sub-agent inherits the main policy/compactor/usage so it can't run away
    assert sub.policy is agent.policy
    assert sub.compactor is agent.compactor
    assert sub.usage is agent.usage
