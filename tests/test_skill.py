import json
import os
import tempfile

from ohwang.prompts import build_system_prompt
from ohwang.skills.loader import Skill, SkillLoader, _parse_frontmatter
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
    assert skills["debug"].path.endswith("SKILL.md")


def test_skill_loader_user_skills_json():
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


def test_skill_loader_user_skills_skill_md():
    d = tempfile.mkdtemp()
    skill_dir = os.path.join(d, ".ohwang", "skills", "greet")
    os.makedirs(skill_dir, exist_ok=True)
    with open(os.path.join(skill_dir, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write(
            "---\n"
            "name: greet\n"
            "description: Greet the user politely.\n"
            "allowed-tools:\n"
            "  - bash\n"
            "  - file_read\n"
            "---\n"
            "\n"
            "Say hello warmly.\n"
        )

    loader = SkillLoader(d)
    skills = loader.load_all()
    assert "greet" in skills
    s = skills["greet"]
    assert s.source == "user"
    assert s.description == "Greet the user politely."
    assert s.prompt == "Say hello warmly."
    assert s.tools == ["bash", "file_read"]


def test_parse_frontmatter():
    fm, body = _parse_frontmatter(
        "---\n"
        "name: debug\n"
        "description: 'Quoted desc'\n"
        "allowed-tools: [bash, file_read]\n"
        "enabled: true\n"
        "count: 3\n"
        "---\n"
        "\n"
        "Body text.\n"
    )
    assert fm["name"] == "debug"
    assert fm["description"] == "Quoted desc"
    assert fm["allowed-tools"] == ["bash", "file_read"]
    assert fm["enabled"] is True
    assert fm["count"] == 3
    assert body == "Body text."


def test_parse_frontmatter_missing():
    fm, body = _parse_frontmatter("# just a doc\n\nno frontmatter here")
    assert fm == {}
    assert "frontmatter" in body


def test_describe_all():
    loader = SkillLoader(tempfile.mkdtemp())
    loader.load_all()
    lines = loader.describe_all()
    assert any(l.startswith("- debug:") for l in lines)
    assert any(l.startswith("- verify:") for l in lines)


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


def test_system_prompt_injects_skills():
    prompt = build_system_prompt(
        workdir=tempfile.mkdtemp(), skills=["- debug: Debug a failing test"]
    )
    assert "Available skills" in prompt
    assert "- debug: Debug a failing test" in prompt


def test_system_prompt_without_skills():
    prompt = build_system_prompt(workdir=tempfile.mkdtemp())
    assert "Available skills" not in prompt
