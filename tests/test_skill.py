import json
import os
import tempfile

from ohwang.skills.loader import Skill, SkillLoader
from ohwang.skills.tool import SkillTool


def test_skill_loader_bundled():
    loader = SkillLoader(tempfile.mkdtemp())
    skills = loader.load_all()
    assert "debug" in skills
    assert "verify" in skills
    assert "simplify" in skills
    assert "remember" in skills
    assert skills["debug"].source == "bundled"
    assert skills["debug"].prompt != ""
    assert "bash" in skills["debug"].tools


def test_skill_loader_user_skills():
    d = tempfile.mkdtemp()
    skill_dir = os.path.join(d, ".ohwang", "skills")
    os.makedirs(skill_dir, exist_ok=True)
    with open(os.path.join(skill_dir, "custom.json"), "w", encoding="utf-8") as f:
        json.dump({
            "name": "custom",
            "description": "My custom skill",
            "prompt": "Do custom things",
            "tools": ["bash"],
        }, f)

    loader = SkillLoader(d)
    skills = loader.load_all()
    assert "custom" in skills
    assert skills["custom"].source == "user"
    assert "debug" in skills


def test_skill_tool_execute():
    loader = SkillLoader(tempfile.mkdtemp())
    loader.load_all()
    tool = SkillTool(loader)
    r = tool.execute({"name": "debug"})
    assert r.is_error is False
    assert "debug" in r.content.lower()


def test_skill_tool_with_context():
    loader = SkillLoader(tempfile.mkdtemp())
    loader.load_all()
    tool = SkillTool(loader)
    r = tool.execute({"name": "debug", "context": "test failing in foo.py"})
    assert r.is_error is False
    assert "failing in foo.py" in r.content


def test_skill_tool_unknown():
    loader = SkillLoader(tempfile.mkdtemp())
    loader.load_all()
    tool = SkillTool(loader)
    r = tool.execute({"name": "nonexistent"})
    assert r.is_error is True
    assert "Unknown skill" in r.content


def test_skill_dataclass():
    s = Skill(name="test", description="desc", prompt="p", tools=["a", "b"])
    assert s.name == "test"
    assert len(s.tools) == 2
