---
name: readme-writer
description: Creates and writes professional README.md files for software projects. Use when the user asks to write a README, create documentation, or generate project docs from existing code or a description.
license: Apache-2.0
metadata:
  author: example-org
  version: "1.0"
---

# README Writer

## Overview

Generate a complete, professional README.md and write it to disk. The output should be clear enough for a first-time contributor to understand the project, set it up locally, and start contributing.

## Step 1: Gather Context

Look for project context before asking the user:

```bash
ls -la
cat package.json 2>/dev/null || cat pyproject.toml 2>/dev/null || cat go.mod 2>/dev/null
```

## Step 2: README Structure

Every README must include:

1. **Project name and one-line description**
2. **Badges** (CI status, version, license)
3. **Features** — bullet list of key capabilities
4. **Installation** — exact commands to get running
5. **Usage** — at least one real-world example
6. **Contributing** — how to open a PR
7. **License**

## Step 3: Write the File

Write the README directly to disk:

```bash
cat > README.md << 'EOF'
# Project Name

> One-line description

...content...
EOF
```

## Quality Standards

- Use active voice and present tense
- Keep sentences short and scannable
- All code snippets must be tested and runnable
- Avoid marketing language — be direct and specific

## Edge Cases

- If the project has no license file, ask the user which license to use before writing
- For monorepos, write a root README plus individual README files per package
- If documentation already exists, read it first and extend rather than overwrite
