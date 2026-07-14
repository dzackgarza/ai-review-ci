# Source Policing in Tests

> **Style card `SOURCE-POLICING`.** Load this before designing the relevant boundary. After a policy finding, use the same card to replace the bad shape and prove the preferred construction.

## Bad pattern: A test reads the source code of the application and asserts that certain strings, patterns, or symbols do or do not appear in the text.
Examples: asserting `"fallback" not in source` to verify there are no fallback branches, scanning files for deprecated function names, asserting on line counts.

```python
# BAD: test asserts on source code text
def test_no_fallback():
    source = Path("src/module.py").read_text()
    assert "fallback" not in source  # source policing instead of behavior testing
```

## Preferred construction: Move source-text assertions to global QC (lint rules, AST checks, dedicated static analysis).
Tests assert on runtime behavior, not on source text.
The runtime behavior — whether a fallback is actually reachable — is what matters; source text is an unreliable proxy.

```python
# ## Preferred construction: test the runtime behavior
def test_no_fallback_used():
    result = process_with_valid_input()
    assert result == expected_output  # tests behavior, not source text
    # Fallback reachability is a static analysis concern, not a test concern.

# If static enforcement is needed:
# .semgrep/ or .pre-commit-config.yaml — not in a test file
```

## Use this pattern when:
- The test reads `.py`, `.ts`, `.rs`, or other source files as strings and asserts on their text content.
- The assertion is about code structure rather than runtime behavior.
- A lint rule or AST check exists that could enforce the same constraint.

## Choose a different pattern when:
- The test operates on generated/compiled code (not hand-written source) and verifies code generation output.
- The test is explicitly a meta-test that validates codegen templates produce expected output.
