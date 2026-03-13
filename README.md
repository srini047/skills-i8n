# 🌐 skill-i18n
<img src="https://raw.githubusercontent.com/srini047/skills-i8n/refs/heads/master/assets/skill_i18n_user_flow.svg">

> **i18n for AI Agent Skills** — translate your `SKILL.md` repository to any of 83+ languages, powered by [Lingo.dev](https://lingo.dev).

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![uv](https://img.shields.io/badge/packaged%20with-uv-purple.svg)](https://github.com/astral-sh/uv)
[![Powered by Lingo.dev](https://img.shields.io/badge/i18n-lingo.dev-cyan.svg)](https://lingo.dev)
[![Agent Skills](https://img.shields.io/badge/standard-agentskills.io-green.svg)](https://agentskills.io)
[![License](https://img.shields.io/badge/license-Apache%202.0-orange.svg)](LICENSE)

---

AI agents are going global. Your skills should too.

`skill-i18n` takes any skills repository following the [Agent Skills open standard](https://agentskills.io/specification) and translates every `SKILL.md` — frontmatter, descriptions, instructions, and all — into the language your team (or your agent's users) actually speaks.

It preserves code blocks, structure, and technical terms. It copies companion files (`scripts/`, `references/`, `assets/`) untouched. And it does it all concurrently, in seconds.

---

## ✨ Features

- **Full SKILL.md support** — translates `name`, `description`, and the entire Markdown body
- **Structure-aware** — code blocks, headings, tables are preserved; only human-readable text is translated
- **Technical glossary** — agent-domain terms (`SKILL.md`, `Claude`, `MCP`, `LLM`, `API`) are never mistranslated
- **Concurrent translation** — configurable parallelism for large skill repos
- **Companion file preservation** — `scripts/`, `references/`, `assets/` are copied as-is
- **Auto-discovery** — finds skills in flat repos, `skills/*/`, `.claude/skills/*/`, `.agents/skills/*/`
- **Language detection** — auto-detect the source locale of any `SKILL.md`
- **83+ locales** — everything Lingo.dev supports
- **Incremental** — skips already-translated files; use `--overwrite` to force

---

## 📦 Installation

Requires Python 3.11+ and [uv](https://github.com/astral-sh/uv).

```bash
# Clone the repo
git clone https://github.com/your-org/skill-i18n
cd skill-i18n

# Install with uv
uv sync

# Set your Lingo.dev API key
export LINGODOTDEV_API_KEY=your_key_here
export LINGODOTDEV_ENGINE_ID=your_engine_id # optional
```

Get a free API key at [lingo.dev](https://lingo.dev).

---

## 🚀 Quick Start

```bash
# Translate a skills repo to Japanese
uv run skill-i18n translate ./my-skills de

# Translate to Spanish, output to a custom directory
uv run skill-i18n translate ./my-skills es --output ./translated-skills

# Translate to multiple languages (run in sequence or script it)
for locale in fr de ko zh pt-BR; do
  uv run skill-i18n translate ./my-skills $locale --output ./i18n
done

# Scan what's in a repo before translating
uv run skill-i18n scan ./my-skills

# See all supported locales
skill-i18n list-locales

# Filter locales by name
uv run  skill-i18n list-locales --filter chinese

# Auto-detect the language of a SKILL.md
uv run  skill-i18n detect ./my-skills/pdf-processing/SKILL.md
```

---

## 📁 Output Structure

Given a skills repo like:

```
my-skills/
├── pdf-processing/
│   ├── SKILL.md
│   └── scripts/
│       └── extract.py
├── readme-writer/
│   └── SKILL.md
└── code-review/
    └── SKILL.md
```

Running `uv run skill-i18n translate ./my-skills de --output ./i18n` produces:

```
i18n/
└── de/
    ├── pdf-processing/
    │   ├── SKILL.md          ← translated
    │   └── scripts/
    │       └── extract.py    ← copied as-is
    ├── readme-writer/
    │   └── SKILL.md          ← translated
    └── code-review/
        └── SKILL.md          ← translated
```

---

## 🏗️ How It Works

1. **Discover** — walks the repo finding all `SKILL.md` files using standard agent skill path conventions
2. **Parse** — extracts YAML frontmatter and Markdown body from each skill
3. **Translate frontmatter** — sends `name` + `description` as a structured object to Lingo.dev's `localize_object` API, preserving field relationships
4. **Translate body** — wraps Markdown in HTML (protecting code blocks with `<pre><code>`) and calls `localize_html` to preserve structure
5. **Glossary** — passes an agent-domain glossary as reference data so technical terms stay consistent
6. **Reconstruct** — renders valid `SKILL.md` with translated content, original license, and unchanged frontmatter fields
7. **Copy companions** — duplicates `scripts/`, `references/`, `assets/` into the output directory

---

## 🌍 Supported Languages

83+ languages including:

| Code | Language | Code | Language |
|------|----------|------|----------|
| `es` | Spanish | `ja` | Japanese |
| `fr` | French | `ko` | Korean |
| `de` | German | `zh` | Chinese (Simplified) |
| `hi` | Hindi | `ru` | Russian |
| `it` | Italian | `nl` | Dutch |

Run `uv run skill-i18n list-locales` for the complete list.

---

## ⚙️ CLI Reference

### `translate`

```
uv run skill-i18n translate REPO_PATH TARGET_LOCALE [OPTIONS]

Arguments:
  REPO_PATH       Path to your skills repository
  TARGET_LOCALE   Target locale code (e.g. es, ja, pt-BR)

Options:
  --output, -o    Output directory (default: REPO_PATH/i18n/)
  --source, -s    Source locale (default: en)
  --api-key       Lingo.dev API key (or set LINGODOTDEV_API_KEY)
  --engine-id     Lingo.dev engine ID (optional)
  --concurrency   Max parallel requests, 1-10 (default: 3)
  --overwrite     Overwrite existing translated files
```

### `scan`

```
uv run skill-i18n scan REPO_PATH

Lists all discovered SKILL.md files with name, description, and path.
```

### `list-locales`

```
uv run skill-i18n list-locales [--filter TEXT]

Lists all 83+ supported locales. Filter by name or code.
```

### `detect`

```
uv run  skill-i18n detect SKILL_PATH

Detects the source language of a SKILL.md file.
```

---

## 🧪 Running Tests

```bash
uv run pytest tests/ -v
```

Tests use mocked Lingo.dev responses — no API key required.

---

## 🏗️ Project Structure

```
skill-i18n/
├── skill_i18n/
│   ├── __init__.py        # blank
│   ├── cli.py             # Typer CLI with Rich output
│   ├── parser.py          # SKILL.md frontmatter + body parser
│   ├── repo.py            # Repo discovery and translation orchestration
│   └── translator.py      # Lingo.dev SDK wrapper
├── tests/
│   ├── __init__.py        # blank
│   ├── test_parser.py     # Parser unit tests
│   └── test_translator.py # Translator unit tests (mocked)
├── example_skills/        # Sample skills repo for testing
│   ├── pdf-processing/
│   ├── readme-writer/
│   └── code-review/
├── pyproject.toml
└── README.md
```

---

## 🤝 Contributing

1. Fork the repo
2. Create a feature branch
3. Run tests: `uv run pytest`
4. Open a PR

---

## 📄 License

Apache 2.0 — see [LICENSE](LICENSE).

---

Built at a hackathon because agents deserve to speak every language. 🚀
