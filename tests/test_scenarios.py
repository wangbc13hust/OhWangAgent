"""Office-agent scenario tests.

Each test drives the full agent loop with a scripted provider and asserts real
filesystem/todo/session side effects, simulating everyday office workflows:
meeting notes, archiving, todo-driven reports, data extraction, web research,
batch editing, save/resume, clarifying questions, delegation, and plan mode.
"""

import json
from unittest.mock import patch

from ohwang.modes import Mode
from ohwang.services.session import SessionStore
from ohwang.tools.agent_tool import AgentTool
from tests.helpers import build_agent


def _tool_results(agent):
    return [
        b
        for m in agent.messages
        for b in (m["content"] if isinstance(m.get("content"), list) else [])
        if b.get("type") == "tool_result"
    ]


def test_scenario_meeting_notes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    responses = [
        [
            {"type": "text", "text": "我来生成会议纪要。"},
            {
                "type": "tool_use",
                "id": "t1",
                "name": "file_write",
                "input": {
                    "file_path": "meeting-2026-08-01.md",
                    "content": "# 周会纪要\n- 决策: 下周三发布 v0.4\n- 负责人: 张三",
                },
            },
        ],
        [{"type": "text", "text": "会议纪要已保存到 meeting-2026-08-01.md。"}],
    ]
    agent, _ = build_agent(responses)
    final = agent.run("请把今天的周会内容写成一份会议纪要")
    assert "已保存" in final
    content = (tmp_path / "meeting-2026-08-01.md").read_text(encoding="utf-8")
    assert "周会纪要" in content
    assert "下周三发布" in content


def test_scenario_document_archive(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "draft.txt").write_text("旧方案草稿", encoding="utf-8")
    (tmp_path / "final.txt").write_text("最终方案", encoding="utf-8")
    responses = [
        [
            {"type": "text", "text": "我来归档文档。"},
            {
                "type": "tool_use",
                "id": "t1",
                "name": "file_write",
                "input": {"file_path": "archive/2026/draft.txt", "content": "旧方案草稿"},
            },
            {
                "type": "tool_use",
                "id": "t2",
                "name": "file_write",
                "input": {"file_path": "archive/2026/final.txt", "content": "最终方案"},
            },
        ],
        [{"type": "text", "text": "归档完成，共 2 份。"}],
    ]
    agent, _ = build_agent(responses)
    final = agent.run("把当前目录的文档归档到 archive/2026 文件夹")
    assert "归档完成" in final
    assert (tmp_path / "archive" / "2026" / "draft.txt").exists()
    assert (tmp_path / "archive" / "2026" / "final.txt").exists()
    assert (tmp_path / "archive" / "2026" / "final.txt").read_text(
        encoding="utf-8"
    ) == "最终方案"


def test_scenario_todo_driven_report(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    responses = [
        [
            {"type": "text", "text": "我先列一个任务清单。"},
            {
                "type": "tool_use",
                "id": "t1",
                "name": "todo_write",
                "input": {
                    "todos": [
                        {"content": "收集数据", "status": "in_progress", "priority": "high"},
                        {"content": "写报告", "status": "pending", "priority": "high"},
                    ]
                },
            },
        ],
        [
            {"type": "text", "text": "开始写报告。"},
            {
                "type": "tool_use",
                "id": "t2",
                "name": "file_write",
                "input": {
                    "file_path": "report.md",
                    "content": "# 季度报告\n数据已收集，结论通过。",
                },
            },
            {
                "type": "tool_use",
                "id": "t3",
                "name": "todo_write",
                "input": {
                    "todos": [
                        {"content": "收集数据", "status": "completed", "priority": "high"},
                        {"content": "写报告", "status": "completed", "priority": "high"},
                    ]
                },
            },
        ],
        [{"type": "text", "text": "全部完成。"}],
    ]
    agent, _ = build_agent(responses)
    final = agent.run("按清单完成季度报告")
    assert "全部完成" in final
    assert (tmp_path / "report.md").exists()
    statuses = {t["content"]: t["status"] for t in agent.todo_store.todos}
    assert statuses == {"收集数据": "completed", "写报告": "completed"}


def test_scenario_data_extraction(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "sales-01.txt").write_text("销售额 1200 万元\n", encoding="utf-8")
    (tmp_path / "sales-02.txt").write_text("销售额 800 万元\n", encoding="utf-8")
    responses = [
        [
            {"type": "text", "text": "我先检索所有销售数据。"},
            {
                "type": "tool_use",
                "id": "t1",
                "name": "grep",
                "input": {"pattern": "销售额", "path": str(tmp_path)},
            },
        ],
        [
            {"type": "text", "text": "汇总成报告。"},
            {
                "type": "tool_use",
                "id": "t2",
                "name": "file_write",
                "input": {
                    "file_path": "sales-summary.md",
                    "content": "# 销售汇总\n总计 2000 万元。",
                },
            },
        ],
        [{"type": "text", "text": "汇总完成。"}],
    ]
    agent, _ = build_agent(responses)
    agent.run("从销售文件中提取数据并汇总成报告")
    content = (tmp_path / "sales-summary.md").read_text(encoding="utf-8")
    assert "2000" in content
    results = _tool_results(agent)
    assert "sales-01.txt" in results[0]["content"]
    assert "sales-02.txt" in results[0]["content"]


def test_scenario_research_report(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mock_resp = type(
        "Resp",
        (),
        {
            "text": "<html><body>GDP growth 5% in 2026</body></html>",
            "status_code": 200,
            "headers": {"content-type": "text/html"},
        },
    )()
    responses = [
        [
            {"type": "text", "text": "先搜索再抓取。"},
            {
                "type": "tool_use",
                "id": "t1",
                "name": "web_search",
                "input": {"query": "2026 经济增速"},
            },
            {
                "type": "tool_use",
                "id": "t2",
                "name": "web_fetch",
                "input": {"url": "https://example.com/econ"},
            },
        ],
        [
            {"type": "text", "text": "写调研报告。"},
            {
                "type": "tool_use",
                "id": "t3",
                "name": "file_write",
                "input": {
                    "file_path": "research.md",
                    "content": "# 调研报告\n2026 年 GDP 增速 5%。",
                },
            },
        ],
        [{"type": "text", "text": "报告完成。"}],
    ]
    with patch("ohwang.tools.web_fetch.httpx.get", return_value=mock_resp):
        agent, _ = build_agent(responses)
        final = agent.run("调研 2026 经济形势并输出报告")
    assert "报告完成" in final
    content = (tmp_path / "research.md").read_text(encoding="utf-8")
    assert "5%" in content


def test_scenario_batch_edit(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "doc1.txt").write_text("部门: 市场部\n", encoding="utf-8")
    (tmp_path / "doc2.txt").write_text("部门: 市场部\n", encoding="utf-8")
    responses = [
        [
            {"type": "text", "text": "先找出包含旧部门名的文件。"},
            {
                "type": "tool_use",
                "id": "t1",
                "name": "grep",
                "input": {"pattern": "市场部", "path": str(tmp_path), "include": "*.txt"},
            },
        ],
        [
            {"type": "text", "text": "逐个更新。"},
            {
                "type": "tool_use",
                "id": "t2",
                "name": "file_edit",
                "input": {
                    "file_path": str(tmp_path / "doc1.txt"),
                    "old_string": "市场部",
                    "new_string": "销售部",
                },
            },
            {
                "type": "tool_use",
                "id": "t3",
                "name": "file_edit",
                "input": {
                    "file_path": str(tmp_path / "doc2.txt"),
                    "old_string": "市场部",
                    "new_string": "销售部",
                },
            },
        ],
        [{"type": "text", "text": "已批量更新。"}],
    ]
    agent, _ = build_agent(responses)
    final = agent.run("把公司文档里的“市场部”统一改成“销售部”")
    assert "批量更新" in final
    assert "销售部" in (tmp_path / "doc1.txt").read_text(encoding="utf-8")
    assert "销售部" in (tmp_path / "doc2.txt").read_text(encoding="utf-8")


def test_scenario_save_resume(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    responses = [
        [
            {
                "type": "tool_use",
                "id": "t1",
                "name": "file_write",
                "input": {"file_path": "draft.md", "content": "草稿内容"},
            }
        ],
        [{"type": "text", "text": "草稿已写好。"}],
    ]
    agent, _ = build_agent(responses)
    agent.run("写一份草稿")
    store = SessionStore(str(tmp_path / ".ohwang"))
    sid = store.save(agent.messages, preview="draft")
    loaded = store.load(sid)
    assert loaded is not None
    assert len(loaded) == len(agent.messages)

    agent2, _ = build_agent([])
    agent2.messages = loaded
    assert any("draft.md" in json.dumps(m, ensure_ascii=False) for m in agent2.messages)


def test_scenario_ask_user_then_write(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    responses = [
        [
            {"type": "text", "text": "先确认格式。"},
            {
                "type": "tool_use",
                "id": "t1",
                "name": "ask_user_question",
                "input": {
                    "question": "报告用什么格式?",
                    "header": "格式",
                    "options": [{"label": "Markdown"}, {"label": "Word"}],
                },
            },
        ],
        [
            {"type": "text", "text": "按 Markdown 写。"},
            {
                "type": "tool_use",
                "id": "t2",
                "name": "file_write",
                "input": {"file_path": "out.md", "content": "# 报告\nMarkdown 格式"},
            },
        ],
        [{"type": "text", "text": "完成。"}],
    ]
    agent, _ = build_agent(responses)
    from ohwang.tools.ask_user import AskUserQuestionTool

    agent.tools.register(AskUserQuestionTool(lambda q, opts: opts[0]["label"]))
    final = agent.run("帮我生成一份报告")
    assert "完成" in final
    assert (tmp_path / "out.md").exists()
    assert (tmp_path / "out.md").read_text(encoding="utf-8") == "# 报告\nMarkdown 格式"


def test_scenario_subagent_delegation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    responses = [
        [
            {"type": "text", "text": "委派子 agent。"},
            {
                "type": "tool_use",
                "id": "t1",
                "name": "agent",
                "input": {"description": "整理清单", "prompt": "整理一份文件清单"},
            },
        ],
        [{"type": "text", "text": "子 agent 已返回。"}],
    ]
    agent, _ = build_agent(responses)

    sub_responses = [
        [
            {
                "type": "tool_use",
                "id": "s1",
                "name": "file_write",
                "input": {"file_path": "inventory.txt", "content": "文件: A, B, C"},
            }
        ],
        [{"type": "text", "text": "清单: 文件 A/B/C"}],
    ]

    def factory():
        sub_agent, _ = build_agent(sub_responses)
        return sub_agent

    agent.tools.register(AgentTool(factory))
    final = agent.run("让子 agent 整理文件清单")
    assert "子 agent 已返回" in final
    assert (tmp_path / "inventory.txt").exists()
    assert (tmp_path / "inventory.txt").read_text(encoding="utf-8") == "文件: A, B, C"


def test_scenario_plan_then_execute(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "spec.txt").write_text("需求说明", encoding="utf-8")
    responses = [
        [
            {"type": "text", "text": "先进入计划模式调研。"},
            {"type": "tool_use", "id": "t1", "name": "enter_plan_mode", "input": {}},
            {
                "type": "tool_use",
                "id": "t2",
                "name": "file_read",
                "input": {"file_path": str(tmp_path / "spec.txt")},
            },
        ],
        [
            {"type": "text", "text": "计划完毕，开始执行。"},
            {"type": "tool_use", "id": "t3", "name": "exit_plan_mode", "input": {}},
            {
                "type": "tool_use",
                "id": "t4",
                "name": "file_write",
                "input": {"file_path": "impl.py", "content": "def main(): pass"},
            },
        ],
        [{"type": "text", "text": "完成。"}],
    ]
    agent, _ = build_agent(responses)
    # Exiting plan mode now requires explicit user approval; simulate the user
    # approving so the model can proceed to the write phase.
    agent.permissions._ask = lambda name, inp: "allow"
    final = agent.run("先调研需求再实现")
    assert "完成" in final
    assert (tmp_path / "impl.py").exists()
    assert agent.permissions.mode is Mode.AUTO  # restored after exiting plan mode
