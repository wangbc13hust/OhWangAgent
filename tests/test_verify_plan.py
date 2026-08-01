from ohwang.tools.verify_plan import VerifyPlanExecutionTool


def test_verify_all_done():
    tool = VerifyPlanExecutionTool()
    r = tool.execute(
        {
            "steps": [
                {"step": "读需求", "status": "done", "evidence": "文件已读"},
                {"step": "写报告", "status": "done", "evidence": "报告已保存"},
            ]
        }
    )
    assert not r.is_error
    assert "2/2 done" in r.content
    assert "All planned steps completed" in r.content


def test_verify_with_missed():
    tool = VerifyPlanExecutionTool()
    r = tool.execute(
        {
            "steps": [
                {"step": "读需求", "status": "done"},
                {"step": "写报告", "status": "missed"},
            ]
        }
    )
    assert r.is_error
    assert "1/2 done" in r.content
    assert "Missed steps remain" in r.content


def test_verify_partial_only():
    tool = VerifyPlanExecutionTool()
    r = tool.execute(
        {
            "steps": [
                {"step": "第一步", "status": "done"},
                {"step": "第二步", "status": "partial", "evidence": "完成一半"},
            ]
        }
    )
    assert not r.is_error
    assert "partial steps remain" in r.content


def test_verify_empty_steps():
    tool = VerifyPlanExecutionTool()
    r = tool.execute({"steps": []})
    assert r.is_error
    assert "Nothing to verify" in r.content


def test_verify_tool_schema():
    tool = VerifyPlanExecutionTool()
    assert tool.name == "verify_plan_execution"
    assert "steps" in tool.input_schema["properties"]
    assert "required" in tool.input_schema
