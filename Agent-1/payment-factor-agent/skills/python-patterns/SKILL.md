---
name: python-patterns
description: Pythonic idioms, type hints, error handling, and best practices for robust Python code. Use when writing, reviewing, or refactoring Python code.
---

# Python Patterns

## Type Hints (Python 3.10+)

```python
def process_items(items: list[str]) -> dict[str, int]:
    return {item: len(item) for item in items}

def get_user(user_id: str) -> User | None:
    return db.find(user_id)
```

## Error Handling

```python
# Specific exceptions with chaining
try:
    data = json.loads(raw)
except json.JSONDecodeError as e:
    raise ValueError(f"Invalid JSON input") from e

# Custom hierarchy
class AppError(Exception): pass
class NotFoundError(AppError): pass
class ValidationError(AppError): pass
```

## Data Classes

```python
from dataclasses import dataclass, field
from datetime import datetime, timezone

@dataclass
class PipelineResult:
    pallet_ids: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if not self.pallet_ids:
            raise ValueError("At least one pallet ID required")
```

## Context Managers

```python
from contextlib import contextmanager

@contextmanager
def timer(name: str):
    start = time.perf_counter()
    yield
    elapsed = time.perf_counter() - start
    logger.info("%s took %.2fs", name, elapsed)
```

## Generators for Large Data

```python
def read_large_file(path: str) -> Iterator[str]:
    with open(path) as f:
        for line in f:
            yield line.strip()
```

## Concurrency

```python
# ThreadPoolExecutor for I/O-bound (API calls, file ops)
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
    results = list(pool.map(fetch_url, urls))

# ProcessPoolExecutor for CPU-bound (data processing)
with concurrent.futures.ProcessPoolExecutor() as pool:
    results = list(pool.map(process_chunk, chunks))
```

## Quick Reference

| Pattern | Use |
|---------|-----|
| `pathlib.Path` | All file path operations |
| f-strings | String formatting |
| `enumerate()` | Index + element loops |
| `dataclass` | Data containers |
| `contextmanager` | Resource management |
| `functools.wraps` | Decorator preservation |
| Generator expressions | Lazy evaluation for large data |

## Anti-Patterns

- Mutable default arguments (`def f(items=[])`)
- Bare `except:` without specific exception
- `type(x) == list` instead of `isinstance(x, list)`
- `x == None` instead of `x is None`
- `from module import *`
- String concatenation in loops (use `"".join()`)
