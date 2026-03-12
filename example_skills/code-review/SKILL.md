---
name: code-review
description: Performs thorough code reviews covering bugs, security vulnerabilities, performance, and style. Use when the user asks to review code, check a pull request, or audit a file for issues.
license: Apache-2.0
metadata:
  author: example-org
  version: "1.0"
---

# Code Review Skill

## Overview

Perform a structured code review across four dimensions: correctness, security, performance, and style. Always be constructive and explain the reasoning behind each suggestion.

## Review Dimensions

### 1. Correctness

Check for:
- Logic errors and off-by-one mistakes
- Unhandled edge cases (empty inputs, null values, overflow)
- Incorrect error handling or swallowed exceptions
- Race conditions in concurrent code

### 2. Security

Check for:
- SQL injection or command injection vectors
- Hardcoded secrets or API keys
- Improper input validation
- Insecure deserialization

### 3. Performance

Check for:
- N+1 query patterns
- Unnecessary memory allocation in loops
- Missing indexes on frequently queried fields
- Blocking calls in async contexts

### 4. Style

Check for:
- Naming consistency (follow existing conventions in the codebase)
- Functions longer than 50 lines (split them)
- Missing or outdated comments
- Dead code

## Output Format

Structure feedback as:

```
## Summary
<2-3 sentence overview>

## Issues Found

### 🔴 Critical
- [file:line] Description of issue and why it matters

### 🟡 Suggestions  
- [file:line] Description of improvement

### ✅ Looks Good
- Well-implemented patterns worth noting
```

## Guidelines

- Always explain *why* something is an issue, not just *what* to change
- Provide a concrete fix or code snippet where helpful
- Limit feedback to 10 most important issues to avoid overwhelming the author
- Distinguish between blocking issues and optional suggestions
