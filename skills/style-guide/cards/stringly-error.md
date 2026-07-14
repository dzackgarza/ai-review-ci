# String-Based Error Types

> **Style card `STRINGLY-ERROR`.** Load this before designing the relevant boundary. After a policy finding, use the same card to replace the bad shape and prove the preferred construction.

## Bad pattern: Errors are represented as strings (string literals, error messages, or string enums) that force callers to match on exact text rather than structured error types.
This makes error handling brittle, tests assert on message wording instead of error semantics, and catch-all handling becomes inevitable.

```python
# BAD: stringly error
def process_file(path):
    if not os.path.exists(path):
        return "file not found"  # string error
    # ... caller must compare strings

# BAD: exact string assertion in test
assert "file not found" in str(result)
```

## Preferred construction: Define domain error types as explicit classes, enums, or exception types.
Assert on error type/tag, not error message.
Tests that need to verify error semantics should match on the error kind, not the rendered text.

```python
# ## Preferred construction: domain error type
class FileError(Exception):
    def __init__(self, kind: str, path: str):
        self.kind = kind  # "not_found", "permission_denied", etc.
        self.path = path

# ## Preferred construction: test asserts on error type, not message
with pytest.raises(FileError) as exc:
    process_file("/nonexistent")
assert exc.value.kind == "not_found"
```

## Use this pattern when:
- Callers use string comparisons to distinguish error cases.
- Tests assert on error message text rather than error type.
- Error handling uses broad `except` because the error type is too vague.

## Choose a different pattern when:
- The string is a user-facing message that is also the error identifier (and a structured alternative exists for programmatic handling).
- The error is from an external library where you cannot control the type.
