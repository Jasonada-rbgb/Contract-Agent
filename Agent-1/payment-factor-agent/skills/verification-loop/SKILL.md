---
name: verification-loop
description: Comprehensive verification system. Run build, type check, lint, test, and security checks after completing features or before creating PRs. Use after significant code changes or refactoring.
---

# Verification Loop

Run after completing a feature, before a PR, or after refactoring.

## Verification Phases

### Phase 1: Build
```powershell
# Python
py -m py_compile your_module.py

# Node
npm run build 2>&1 | Select-Object -Last 20
```
If build fails, STOP and fix before continuing.

### Phase 2: Type Check
```powershell
# Python
pyright . 2>&1 | Select-Object -First 30
# or: py -m mypy . --ignore-missing-imports

# TypeScript
npx tsc --noEmit
```

### Phase 3: Lint
```powershell
# Python
ruff check . 2>&1 | Select-Object -First 30

# JS/TS
npm run lint 2>&1 | Select-Object -First 30
```

### Phase 4: Test Suite
```powershell
# Python
py -m pytest --cov=agent_server --cov-fail-under=80 -q

# Node
npm test -- --coverage 2>&1 | Select-Object -Last 50
```
Target: 80% minimum coverage.

### Phase 5: Security Scan
```powershell
# Check for secrets
rg "sk-|dapi|api_key|password\s*=" --type py . | Select-Object -First 10

# Check for debug code
rg "print\(|console\.log|breakpoint\(\)" --type py src/ | Select-Object -First 10
```

### Phase 6: Diff Review
```powershell
git diff --stat
git diff HEAD~1 --name-only
```
Review each changed file for unintended changes, missing error handling, edge cases.

## Output Format

```
VERIFICATION REPORT
==================
Build:     [PASS/FAIL]
Types:     [PASS/FAIL] (X errors)
Lint:      [PASS/FAIL] (X warnings)
Tests:     [PASS/FAIL] (X/Y passed, Z% coverage)
Security:  [PASS/FAIL] (X issues)
Diff:      [X files changed]

Overall:   [READY/NOT READY] for PR
```

## When to Run

- After completing each function or component
- Before moving to the next task
- After refactoring
- Before creating a PR
