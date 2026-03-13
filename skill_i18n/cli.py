"""
skill-i18n CLI — translate your agent skills repo to any language.

Sample Usage:
    skill-i18n translate ./my-skills es
    skill-i18n translate ./my-skills ja --output ./translated
    skill-i18n list-locales
    skill-i18n scan ./my-skills
    skill-i18n detect ./my-skills/pdf-processing/SKILL.md
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text

from .parser import discover_skills, parse_skill_file
from .repo import SkillRepo, TranslationResult
from .translator import LOCALE_NAMES, SUPPORTED_LOCALES

app = typer.Typer(
    name="skill-i18n",
    help="🌐 i18n for AI Agent Skills — powered by Lingo.dev",
    rich_markup_mode="rich",
    add_completion=False,
)
console = Console()

LOGO = (
    "\n[bold cyan] ____  _    _ _ _      _ _  ___  ____  [/bold cyan]\n"
    "[bold cyan]/ ___|| | _(_) | |    (_) |/ _ \\|  _ \\ [/bold cyan]\n"
    "[bold cyan]\\___ \\| |/ / | | |____| | | (_) | | | |[/bold cyan]\n"
    "[bold cyan] ___) |   <| | | |____| | |\\__, | |_| |[/bold cyan]\n"
    "[bold cyan]|____/|_|\\_\\_|_|_|    |_|_|  /_/|____/ [/bold cyan]\n"
    "[dim]i18n for AI Agent Skills · powered by Lingo.dev[/dim]\n"
)


def _require_api_key(api_key: str | None) -> str:
    key = api_key or os.environ.get("LINGODOTDEV_API_KEY", "")
    if not key:
        console.print(
            Panel(
                "[red bold]Missing API key![/red bold]\n\n"
                "Set your Lingo.dev API key:\n"
                "  [cyan]export LINGODOTDEV_API_KEY=your_key_here[/cyan]\n\n"
                "Get a free key at [link=https://lingo.dev]lingo.dev[/link]",
                title="🔑 Authentication Required",
                border_style="red",
            )
        )
        raise typer.Exit(1)
    return key


@app.command()
def translate(
    repo_path: Path = typer.Argument(
        ...,
        help="Path to your skills repository (containing SKILL.md files)",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
    target_locale: str = typer.Argument(
        ...,
        help="Target locale code (e.g. es, ja, fr, pt-BR). Run 'list-locales' to see all.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory. Defaults to <repo_path>/i18n/",
    ),
    source_locale: str = typer.Option(
        "en",
        "--source",
        "-s",
        help="Source locale of the skills (default: en)",
    ),
    api_key: Optional[str] = typer.Option(
        None,
        "--api-key",
        envvar="LINGODOTDEV_API_KEY",
        help="Lingo.dev API key (or set LINGODOTDEV_API_KEY)",
    ),
    engine_id: Optional[str] = typer.Option(
        None,
        "--engine-id",
        "-e",
        envvar="LINGODOTDEV_ENGINE_ID",
        help="Lingo.dev Engine ID",
    ),
    concurrency: int = typer.Option(
        3,
        "--concurrency",
        "-c",
        help="Max parallel translation requests (default: 3)",
        min=1,
        max=10,
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        "-f",
        help="Overwrite existing translated files",
    ),
):
    """
    [bold]Translate all SKILL.md files in a skills repository.[/bold]

    Discovers every SKILL.md, translates frontmatter + body via Lingo.dev,
    and writes localized copies preserving your directory structure.

    [dim]Example:[/dim]
        [cyan]skill-i18n translate ./my-skills ja --output ./translated[/cyan]
    """
    console.print(LOGO)

    if target_locale not in SUPPORTED_LOCALES:
        console.print(
            f"[red]Unknown locale: [bold]{target_locale}[/bold][/red]\n"
            "Run [cyan]skill-i18n list-locales[/cyan] to see all supported locales."
        )
        raise typer.Exit(1)

    key = _require_api_key(api_key)
    output_root = output or (repo_path / "i18n")
    locale_name = LOCALE_NAMES.get(target_locale, target_locale)
    engine_label = engine_id or os.environ.get("LINGODOTDEV_ENGINE_ID") or "[dim]org default[/dim]"

    console.print(
        Panel(
            f"[bold]Repository:[/bold] {repo_path.resolve()}\n"
            f"[bold]Target:[/bold]     {target_locale} · {locale_name}\n"
            f"[bold]Source:[/bold]     {source_locale}\n"
            f"[bold]Output:[/bold]     {output_root.resolve()}\n"
            f"[bold]Engine:[/bold]     {engine_label}\n"
            f"[bold]Threads:[/bold]    {concurrency}",
            title="🌐 skill-i18n Translation Job",
            border_style="cyan",
        )
    )

    repo = SkillRepo(repo_path)
    skills = repo.discover()

    if not skills:
        console.print(
            "[yellow]⚠ No SKILL.md files found in this repository.[/yellow]\n"
            "Make sure your skills follow the Agent Skills standard:\n"
            "  [dim]skills/<name>/SKILL.md[/dim]"
        )
        raise typer.Exit(0)

    console.print(f"\n[bold]Found {len(skills)} skill(s)[/bold] to translate:\n")
    for s in skills:
        rel = s.path.relative_to(repo.repo_path)
        console.print(f"  [dim]•[/dim] [cyan]{s.skill_name}[/cyan] [dim]({rel})[/dim]")

    console.print()

    results: list[TranslationResult] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task(
            f"Translating to [bold]{target_locale}[/bold]…",
            total=len(skills),
        )

        async def on_progress(result: TranslationResult):
            results.append(result)
            icon = (
                "✅"
                if result.success and not result.error.startswith("[skipped")
                else ("⏭" if result.error.startswith("[skipped") else "❌")
            )
            progress.update(
                task,
                advance=1,
                description=f"{icon} [cyan]{result.skill_name}[/cyan]",
            )

        async def run():
            return await repo.translate(
                target_locale=target_locale,
                output_root=output_root,
                api_key=key,
                engine_id=engine_id,
                source_locale=source_locale,
                max_concurrent=concurrency,
                overwrite=overwrite,
                on_progress=on_progress,
            )

        report = asyncio.run(run())

    # Summary table
    table = Table(
        title=f"\n📊 Translation Results — {target_locale} ({locale_name})",
        border_style="cyan",
    )
    table.add_column("Skill", style="bold")
    table.add_column("Status")
    table.add_column("Output Path", style="dim")

    for r in report.results:
        if r.success and not r.error.startswith("[skipped"):
            status = Text("✅ translated", style="green")
        elif r.error.startswith("[skipped"):
            status = Text("⏭  skipped", style="yellow")
        else:
            status = Text(f"❌ {r.error[:50]}", style="red")

        rel_out = (
            r.output_path.relative_to(output_root)
            if r.output_path.is_relative_to(output_root)
            else r.output_path
        )
        table.add_row(r.skill_name, status, str(rel_out))

    console.print(table)

    ok = len(report.succeeded)
    fail = len(report.failed)
    console.print(
        f"\n[bold green]✓ {ok} succeeded[/bold green]"
        + (f"  [bold red]✗ {fail} failed[/bold red]" if fail else "")
        + f"\n[dim]Output: {output_root.resolve()}[/dim]\n"
    )

    if fail:
        raise typer.Exit(1)


@app.command()
def scan(
    repo_path: Path = typer.Argument(
        ...,
        help="Path to skills repository",
        exists=True,
        file_okay=False,
    ),
):
    """
    [bold]Scan a skills repository and list discovered SKILL.md files.[/bold]

    Useful for verifying your repo structure before translating.
    """
    console.print(LOGO)
    repo = SkillRepo(repo_path)
    skills = repo.discover()

    if not skills:
        console.print("[yellow]No SKILL.md files found.[/yellow]")
        raise typer.Exit(0)

    table = Table(title=f"📁 Skills in {repo_path.name}", border_style="cyan")
    table.add_column("Name", style="bold cyan")
    table.add_column("Description")
    table.add_column("License", style="dim")
    table.add_column("Path", style="dim")

    for s in skills:
        try:
            rel = s.path.resolve().relative_to(repo_path.resolve())
        except ValueError:
            rel = s.path
        table.add_row(
            s.skill_name,
            s.frontmatter.description[:80]
            + ("…" if len(s.frontmatter.description) > 80 else ""),
            s.frontmatter.license or "—",
            str(rel),
        )

    console.print(table)
    console.print(f"\n[bold]{len(skills)} skill(s) found.[/bold]")


@app.command(name="list-locales")
def list_locales(
    filter: Optional[str] = typer.Option(
        None, "--filter", "-f", help="Filter by name or code"
    ),
):
    """
    [bold]List all locales supported by Lingo.dev.[/bold]
    """
    console.print(LOGO)

    table = Table(title="🌍 Supported Locales (83+)", border_style="cyan")
    table.add_column("Code", style="bold cyan", width=10)
    table.add_column("Language")

    filtered = [
        (code, name)
        for code, name in LOCALE_NAMES.items()
        if not filter
        or filter.lower() in code.lower()
        or filter.lower() in name.lower()
    ]

    for code, name in sorted(filtered, key=lambda x: x[1]):
        table.add_row(code, name)

    console.print(table)
    console.print(f"\n[dim]{len(filtered)} locale(s) shown.[/dim]")


@app.command()
def detect(
    skill_path: Path = typer.Argument(
        ...,
        help="Path to a SKILL.md file",
        exists=True,
        file_okay=True,
    ),
    api_key: Optional[str] = typer.Option(
        None,
        "--api-key",
        envvar="LINGODOTDEV_API_KEY",
    ),
):
    """
    [bold]Detect the source language of a SKILL.md file.[/bold]

    Useful when you receive skills from other teams and don't know the source locale.
    """
    console.print(LOGO)
    key = _require_api_key(api_key)

    skill = parse_skill_file(skill_path)

    from .translator import SkillTranslator

    async def run():
        t = SkillTranslator(api_key=key)
        # Detect on description + first 500 chars of body
        sample = f"{skill.frontmatter.description}\n{skill.body[:500]}"
        return await t.detect_locale(sample)

    detected = asyncio.run(run())
    locale_name = LOCALE_NAMES.get(detected, detected)

    console.print(
        Panel(
            f"[bold]Skill:[/bold]           {skill.skill_name}\n"
            f"[bold]Detected locale:[/bold] [cyan]{detected}[/cyan] — {locale_name}",
            title="🔍 Language Detection",
            border_style="cyan",
        )
    )


def main():
    app()


if __name__ == "__main__":
    main()
