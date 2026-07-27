---
name: continuous-learning
description: Pattern extraction from coding sessions. Identifies recurring workflows, corrections, and preferences to build reusable knowledge. Use at the end of long sessions or after solving complex problems.
---

# Continuous Learning -- Session Pattern Extraction

## When to Use

- End of a productive coding session
- After solving a complex debugging problem
- When you notice recurring patterns in your workflow
- After a user correction that reveals a preference

## Pattern Types to Extract

| Type | Example | Action |
|------|---------|--------|
| User correction | "Don't use print, use logger" | Create rule: always use logging module |
| Repeated workflow | Always run lint before commit | Document as standard workflow |
| Error resolution | "This error means X, fix with Y" | Create troubleshooting entry |
| Architecture decision | "We use factory pattern for connectors" | Document in architecture notes |
| Tool preference | "Use rg instead of grep" | Update skill/rule |

## Extraction Process

1. **Observe** -- note corrections, repeated actions, preferences expressed during session
2. **Classify** -- is this a code style rule, workflow step, architecture decision, or tool preference?
3. **Validate** -- was this a one-off or a consistent pattern? (confidence scoring)
4. **Record** -- create a rule, update a skill, or add to project documentation

## Confidence Scoring

| Score | Meaning | Action |
|-------|---------|--------|
| Low (1 occurrence) | Tentative | Note but don't enforce |
| Medium (2-3 occurrences) | Likely preference | Suggest when relevant |
| High (4+ occurrences) | Established pattern | Apply automatically |

## Output: Create a Cursor Rule

When a pattern reaches high confidence, create a `.cursor/rules/` file:

```markdown
---
description: "Always use structured logging, never print()"
globs: ["**/*.py"]
alwaysApply: false
---
Use the `logging` module instead of `print()` for all output.
Use `logger = logging.getLogger(__name__)` at module level.
```

## Anti-Patterns

- Extracting patterns from a single occurrence
- Creating rules that conflict with existing ones
- Over-specifying rules (too narrow to be useful)
- Ignoring context (a pattern in one project may not apply to another)
