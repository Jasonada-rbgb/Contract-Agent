---
name: security-review
description: Security checklist for code review. Covers secrets management, input validation, SQL injection, auth, XSS, and dependency security. Use when reviewing code, handling user input, or working with credentials.
---

# Security Review Checklist

## 1. Secrets Management

- No hardcoded API keys, tokens, or passwords in source code
- All secrets in environment variables or secret managers
- `.env` files in `.gitignore`
- No secrets in git history (`git log -p | rg "sk-|api_key"`)

## 2. Input Validation

```python
# Always validate user input
from pydantic import BaseModel, Field

class ClaimInput(BaseModel):
    vin: str = Field(..., pattern=r"^[A-Z0-9]{17}$")
    mileage: int = Field(..., ge=0, le=999999)
    repair_date: date
```

- Whitelist validation (not blacklist)
- Error messages don't leak internal details
- File uploads restricted by size, type, and extension

## 3. SQL Injection Prevention

```python
# NEVER concatenate user input into SQL
# Bad:  f"SELECT * FROM users WHERE id = '{user_id}'"
# Good: cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))

# Spark SQL -- use parameterised queries
# Bad:  spark.sql(f"SELECT * FROM t WHERE col = '{val}'")
# Good: spark.sql("SELECT * FROM t WHERE col = :val", args={"val": val})
```

## 4. Authentication & Authorization

- Verify permissions before sensitive operations
- Token/session validation on every protected endpoint
- Role-based access control where applicable

## 5. Sensitive Data Exposure

```python
# Don't log secrets or PII
logger.info("Processing user %s", user_id)        # Good
logger.info("User login: %s / %s", email, password)  # BAD

# Generic error messages for users
return {"error": "An error occurred"}, 500  # Good
return {"error": str(exc), "stack": traceback}, 500  # BAD
```

## 6. Additional Attack Vectors

- **CSRF**: Verify anti-CSRF tokens on state-changing endpoints.
- **SSRF**: Validate and restrict outbound URLs; never let user input control fetch targets.
- **Path traversal**: Sanitise file paths; reject `../` sequences in user-supplied filenames.

## 7. Dependency Security

```bash
pip-audit            # Python vulnerability scan
npm audit            # Node vulnerability scan
```

## Pre-Deployment Checklist

- [ ] No hardcoded secrets
- [ ] All inputs validated
- [ ] Queries parameterised
- [ ] Auth checks on protected routes
- [ ] No sensitive data in logs or error messages
- [ ] Dependencies scanned (`pip-audit`)
- [ ] HTTPS enforced in production
- [ ] File upload paths sanitised
- [ ] Outbound URLs validated (no SSRF)
