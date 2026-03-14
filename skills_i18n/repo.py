"""
Orchestrator: discovers skills in a repo, translates them, and writes
localized copies while preserving directory structure and companion files.
"""

from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .parser import (
    ParsedSkill,
    SkillFrontmatter,
    discover_skills,
    parse_skill_file,
    render_skill_md,
)
from .translator import SkillTranslator


@dataclass
class TranslationResult:
    skill_name: str
    source_path: Path
    output_path: Path
    target_locale: str
    success: bool
    error: str = ""


@dataclass
class TranslationReport:
    target_locale: str
    output_root: Path
    results: list[TranslationResult] = field(default_factory=list)

    @property
    def succeeded(self) -> list[TranslationResult]:
        return [r for r in self.results if r.success]

    @property
    def failed(self) -> list[TranslationResult]:
        return [r for r in self.results if not r.success]

    @property
    def total(self) -> int:
        return len(self.results)


class SkillRepo:
    """
    Represents a skills repository.
    Discovers, parses, and translates all SKILL.md files within it.
    """

    def __init__(self, repo_path: Path | str):
        self.repo_path = Path(repo_path).resolve()
        if not self.repo_path.exists():
            raise FileNotFoundError(f"Skills repo not found: {self.repo_path}")

    def discover(self) -> list[ParsedSkill]:
        """Discover and parse all SKILL.md files in this repo."""
        skill_files = discover_skills(self.repo_path)
        skills: list[ParsedSkill] = []
        for path in skill_files:
            try:
                skills.append(parse_skill_file(path))
            except (ValueError, Exception):
                # Skip malformed SKILL.md files silently in discovery
                pass
        return skills

    async def translate(
        self,
        target_locale: str,
        output_root: Path,
        api_key: str | None = None,
        engine_id: str | None = None,
        source_locale: str = "en",
        max_concurrent: int = 3,
        overwrite: bool = False,
        on_progress=None,
    ) -> TranslationReport:
        """
        Translate all skills in the repo to the target locale.
        Writes output under output_root/, preserving relative paths.

        Args:
            target_locale: BCP-47 locale code (e.g. "es", "ja", "de")
            output_root: Base directory for translated output
            api_key: Lingo.dev API key (falls back to LINGODOTDEV_API_KEY env)
            engine_id: Lingo.dev Engine ID. Routes through your configured engine
            source_locale: Source language of the skills (default: "en")
            max_concurrent: Max parallel translation requests
            overwrite: Whether to overwrite existing translated files
            on_progress: Optional async callback(result: TranslationResult)
        """
        skills = self.discover()
        translator = SkillTranslator(api_key=api_key, source_locale=source_locale, engine_id=engine_id)
        report = TranslationReport(target_locale=target_locale, output_root=output_root)

        sem = asyncio.Semaphore(max_concurrent)

        async def translate_one(skill: ParsedSkill) -> TranslationResult:
            async with sem:
                try:
                    rel_path = skill.path.resolve().relative_to(self.repo_path.resolve())
                except ValueError:
                    rel_path = Path(skill.path.name)
                out_skill_dir = output_root / target_locale / rel_path.parent
                out_skill_dir.mkdir(parents=True, exist_ok=True)
                out_path = out_skill_dir / "SKILL.md"

                if out_path.exists() and not overwrite:
                    result = TranslationResult(
                        skill_name=skill.skill_name,
                        source_path=skill.path,
                        output_path=out_path,
                        target_locale=target_locale,
                        success=True,
                        error="[skipped — already exists]",
                    )
                    if on_progress:
                        await on_progress(result)
                    return result

                try:
                    translated_fm_dict, translated_body = (
                        await translator.translate_skill(
                            frontmatter_dict=skill.frontmatter.to_dict(),
                            body=skill.body,
                            target_locale=target_locale,
                        )
                    )

                    # Reconstruct frontmatter object with translated fields
                    translated_fm = SkillFrontmatter(
                        name=translated_fm_dict.get("name", skill.frontmatter.name),
                        description=translated_fm_dict.get(
                            "description", skill.frontmatter.description
                        ),
                        license=skill.frontmatter.license,
                        metadata=skill.frontmatter.metadata,
                        raw={
                            **skill.frontmatter.raw,
                            **translated_fm_dict,
                            "license": skill.frontmatter.license,  # never translate license
                        },
                    )

                    output_content = render_skill_md(translated_fm, translated_body)
                    out_path.write_text(output_content, encoding="utf-8")

                    # Copy companion files (scripts/, references/, assets/)
                    _copy_companion_files(skill.skill_dir, out_skill_dir)

                    result = TranslationResult(
                        skill_name=skill.skill_name,
                        source_path=skill.path,
                        output_path=out_path,
                        target_locale=target_locale,
                        success=True,
                    )
                except Exception as exc:
                    result = TranslationResult(
                        skill_name=skill.skill_name,
                        source_path=skill.path,
                        output_path=out_path,
                        target_locale=target_locale,
                        success=False,
                        error=str(exc),
                    )

                if on_progress:
                    await on_progress(result)
                return result

        tasks = [translate_one(skill) for skill in skills]
        results = await asyncio.gather(*tasks)
        report.results = list(results)
        return report


def _copy_companion_files(src_dir: Path, dst_dir: Path) -> None:
    """
    Copy non-SKILL.md companion files from the source skill directory.
    Preserves scripts/, references/, assets/ subdirectories.
    These are NOT translated — they are copied as-is.
    """
    for item in src_dir.iterdir():
        if item.name == "SKILL.md":
            continue
        dst = dst_dir / item.name
        if item.is_dir():
            if not dst.exists():
                shutil.copytree(item, dst)
        elif item.is_file():
            if not dst.exists():
                shutil.copy2(item, dst)
