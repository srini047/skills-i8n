"""Tests for SKILL.md parser."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from skill_i18n.parser import (
    ParsedSkill,
    discover_skills,
    parse_skill_file,
    render_skill_md,
)


VALID_SKILL_MD = textwrap.dedent("""\
    ---
    name: test-skill
    description: A test skill for unit testing purposes.
    license: Apache-2.0
    metadata:
      author: test-author
      version: "1.0"
    ---

    # Test Skill

    ## Overview

    This is a test skill body.

    ```python
    print("hello")
    ```
""")


def write_skill(tmp_path: Path, name: str, content: str) -> Path:
    skill_dir = tmp_path / name
    skill_dir.mkdir()
    p = skill_dir / "SKILL.md"
    p.write_text(content)
    return p


class TestParseSkillFile:
    def test_valid_skill(self, tmp_path):
        path = write_skill(tmp_path, "test-skill", VALID_SKILL_MD)
        skill = parse_skill_file(path)

        assert skill.frontmatter.name == "test-skill"
        assert skill.frontmatter.description == "A test skill for unit testing purposes."
        assert skill.frontmatter.license == "Apache-2.0"
        assert "# Test Skill" in skill.body

    def test_missing_frontmatter_raises(self, tmp_path):
        path = write_skill(tmp_path, "bad", "# No frontmatter here\nJust markdown.")
        with pytest.raises(ValueError, match="missing YAML frontmatter"):
            parse_skill_file(path)

    def test_missing_name_raises(self, tmp_path):
        content = "---\ndescription: Missing name\n---\n\n# Body"
        path = write_skill(tmp_path, "no-name", content)
        with pytest.raises(ValueError, match="missing required 'name'"):
            parse_skill_file(path)

    def test_missing_description_raises(self, tmp_path):
        content = "---\nname: no-desc\n---\n\n# Body"
        path = write_skill(tmp_path, "no-desc", content)
        with pytest.raises(ValueError, match="missing required 'description'"):
            parse_skill_file(path)

    def test_skill_dir_property(self, tmp_path):
        path = write_skill(tmp_path, "test-skill", VALID_SKILL_MD)
        skill = parse_skill_file(path)
        assert skill.skill_dir == path.parent

    def test_skill_name_property(self, tmp_path):
        path = write_skill(tmp_path, "my-skill", VALID_SKILL_MD)
        skill = parse_skill_file(path)
        assert skill.skill_name == "test-skill"  # from frontmatter, not dir name


class TestDiscoverSkills:
    def test_discovers_flat_structure(self, tmp_path):
        write_skill(tmp_path, "skill-a", VALID_SKILL_MD)
        write_skill(tmp_path, "skill-b", VALID_SKILL_MD)
        found = discover_skills(tmp_path)
        assert len(found) == 2

    def test_discovers_nested_skills_dir(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        write_skill(skills_dir, "nested-skill", VALID_SKILL_MD)
        found = discover_skills(tmp_path)
        assert len(found) == 1

    def test_discovers_claude_skills_dir(self, tmp_path):
        claude_dir = tmp_path / ".claude" / "skills"
        claude_dir.mkdir(parents=True)
        write_skill(claude_dir, "claude-skill", VALID_SKILL_MD)
        found = discover_skills(tmp_path)
        assert len(found) == 1

    def test_empty_repo(self, tmp_path):
        found = discover_skills(tmp_path)
        assert found == []


class TestRenderSkillMd:
    def test_roundtrip(self, tmp_path):
        path = write_skill(tmp_path, "test-skill", VALID_SKILL_MD)
        skill = parse_skill_file(path)
        rendered = render_skill_md(skill.frontmatter, skill.body)

        assert "---" in rendered
        assert "name: test-skill" in rendered
        assert "# Test Skill" in rendered

    def test_translated_fields_reflected(self, tmp_path):
        path = write_skill(tmp_path, "test-skill", VALID_SKILL_MD)
        skill = parse_skill_file(path)
        skill.frontmatter.name = "habilidad-de-prueba"
        skill.frontmatter.description = "Una habilidad de prueba."
        rendered = render_skill_md(skill.frontmatter, "# Habilidad\n\nCuerpo traducido.")

        assert "habilidad-de-prueba" in rendered
        assert "Una habilidad de prueba." in rendered
        assert "# Habilidad" in rendered
