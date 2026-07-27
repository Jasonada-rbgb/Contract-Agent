---
name: search-first
description: Research-before-coding workflow. Search for existing tools, libraries, and patterns before writing custom code. Use when starting a new feature, adding dependencies, or before creating utilities.
---

# Search First -- Research Before You Code

## When to Use

- Starting a new feature that likely has existing solutions
- Adding a dependency or integration
- Before creating a new utility, helper, or abstraction
- The user asks "add X functionality" and you're about to write code

## Workflow

1. **Need analysis** -- define what functionality is needed, language/framework constraints
2. **Repo check** -- search the existing codebase first: `rg` through relevant modules
3. **Parallel search** -- check package registries (PyPI/npm), MCP tools, GitHub, web search
4. **Evaluate** -- score candidates on functionality, maintenance, community, docs, license, deps
5. **Security scan** -- run `pip-audit` or `npm audit` on candidate packages before adopting
6. **License check** -- verify the license is compatible (MIT, Apache-2.0, BSD are safe; GPL may impose requirements on your project)
7. **Decide** -- adopt as-is, extend/wrap, compose multiple, or build custom
8. **Implement** -- install package / configure tool / write minimal custom code

## Decision Matrix

| Signal | Action |
|--------|--------|
| Exact match, well-maintained, permissive license | **Adopt** -- install and use |
| Partial match, good foundation | **Extend** -- install + thin wrapper |
| Multiple weak matches | **Compose** -- combine 2-3 small packages |
| Nothing suitable or license-incompatible | **Build** -- custom code, informed by research |

## Quick Check (before writing any utility)

0. Does this already exist in the repo? `rg` through relevant modules first
1. Common problem? Search PyPI/npm
2. Is there a library for this? Check documentation via web search
3. Is there a GitHub implementation? Search for maintained OSS
4. Is the license compatible? Check PyPI/npm page or repo LICENSE file
5. Are there known vulnerabilities? Run `pip-audit` / `npm audit`

## License Compatibility

| License | Safe to use? | Notes |
|---------|-------------|-------|
| MIT, Apache-2.0, BSD | Yes | Permissive, no restrictions |
| LGPL | Usually | Must not statically link (rare in Python/JS) |
| GPL | Caution | May require your code to be GPL too |
| AGPL | Caution | Network use triggers copyleft |
| No license | Avoid | Legally ambiguous |

## Anti-Patterns

- **Jumping to code** without checking if a solution exists
- **Ignoring license** -- adopting GPL code into a proprietary project
- **Skipping security** -- installing packages without vulnerability scan
- **Over-customizing** a library wrapper so heavily it loses its benefits
- **Dependency bloat** -- installing a massive package for one small feature
- **Not checking the repo first** before adding external dependencies
