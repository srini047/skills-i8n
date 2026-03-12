"""
Parser for SKILL.md files following the Agent Skills open standard.
Handles YAML frontmatter + Markdown body format.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)


@dataclass
class SkillFrontmatter:
    name: str
    description: str
    license: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return all frontmatter fields as a dict for translation."""
        return {
            "name": self.name,
            "description": self.description,
            **{k: v for k, v in self.raw.items() if k not in ("name", "description", "license")},
        }


@dataclass
class ParsedSkill:
    path: Path
    frontmatter: SkillFrontmatter
    body: str
    raw_text: str

    @property
    def skill_dir(self) -> Path:
        return self.path.parent

    @property
    def skill_name(self) -> str:
        return self.frontmatter.name or self.path.parent.name


def parse_skill_file(path: Path) -> ParsedSkill:
    """Parse a SKILL.md file into structured components."""
    raw_text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(raw_text)

    if not match:
        raise ValueError(
            f"Invalid SKILL.md at {path}: missing YAML frontmatter. "
            "Expected '---' delimited block at top of file."
        )

    frontmatter_raw = yaml.safe_load(match.group(1)) or {}
    body = match.group(2).strip()

    if "name" not in frontmatter_raw:
        raise ValueError(f"SKILL.md at {path} is missing required 'name' field")
    if "description" not in frontmatter_raw:
        raise ValueError(f"SKILL.md at {path} is missing required 'description' field")

    frontmatter = SkillFrontmatter(
        name=frontmatter_raw["name"],
        description=frontmatter_raw["description"],
        license=frontmatter_raw.get("license", ""),
        metadata=frontmatter_raw.get("metadata", {}),
        raw=frontmatter_raw,
    )

    return ParsedSkill(
        path=path,
        frontmatter=frontmatter,
        body=body,
        raw_text=raw_text,
    )


def discover_skills(repo_path: Path) -> list[Path]:
    """
    Discover all SKILL.md files in a skills repository.

    Searches common agent skill locations:
    - <repo>/skills/*/SKILL.md
    - <repo>/.claude/skills/*/SKILL.md
    - <repo>/.agents/skills/*/SKILL.md
    - <repo>/*/SKILL.md  (flat skill repos like anthropics/skills)
    """
    skill_files: list[Path] = []
    seen: set[Path] = set()

    search_patterns = [
        "SKILL.md",
        "*/SKILL.md",
        "skills/*/SKILL.md",
        ".claude/skills/*/SKILL.md",
        ".agents/skills/*/SKILL.md",
        ".codex/skills/*/SKILL.md",
    ]

    for pattern in search_patterns:
        for match in repo_path.glob(pattern):
            resolved = match.resolve()
            if resolved not in seen:
                seen.add(resolved)
                skill_files.append(match)

    return sorted(skill_files)


def render_skill_md(frontmatter: SkillFrontmatter, body: str) -> str:
    """Reconstruct a SKILL.md file from its components."""
    fm_dict = {**frontmatter.raw}

    # Patch translatable fields back in
    fm_dict["name"] = frontmatter.name
    fm_dict["description"] = frontmatter.description

    yaml_str = yaml.dump(
        fm_dict,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    ).rstrip()

    return f"---\n{yaml_str}\n---\n\n{body}\n"
