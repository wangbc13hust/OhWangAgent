from ohwang.tools.ask_user import AskUserQuestionTool


def test_ask_user_with_callback():
    answers = ["option1"]

    def callback(question, options):
        return answers.pop(0)

    tool = AskUserQuestionTool(callback=callback)
    r = tool.execute({
        "question": "Which framework?",
        "header": "Framework",
        "options": [
            {"label": "option1", "description": "Use option1"},
            {"label": "option2", "description": "Use option2"},
        ],
    })
    assert r.is_error is False
    assert "option1" in r.content


def test_ask_user_without_callback():
    tool = AskUserQuestionTool(callback=None)
    r = tool.execute({
        "question": "Which?",
        "header": "Choice",
        "options": [{"label": "a"}, {"label": "b"}],
    })
    assert r.is_error is False
    assert "non-interactive" in r.content.lower() or "default" in r.content.lower()


def test_ask_user_schema():
    tool = AskUserQuestionTool()
    assert tool.name == "ask_user_question"
    assert tool.default_permission == "allow"
    assert "question" in tool.input_schema["properties"]
    assert "options" in tool.input_schema["properties"]
