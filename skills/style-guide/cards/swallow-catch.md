# try/catch That Swallows or Hedges

> **Style card `SWALLOW-CATCH`.** Load this before designing the relevant boundary. After a policy finding, use the same card to replace the bad shape and prove the preferred construction.

## Bad pattern: A try/catch around an operation that is expected to succeed, converting a useful diagnostic into a silent continuation or a weak log line.

Catching `AssertionError` is worse than ordinary swallowing: an assertion is a proof claim about code state, not a runtime error.
Do not recover from it, translate it, or test it as product behavior.

```python
# BAD: swallows diagnostic
try:
    result = api_call()
except Exception:
    result = None

# BAD: hedges with a log that no one reads
try:
    data = read_file(path)
except Exception as e:
    logger.error(f"failed to read {path}: {e}")
    data = []
```

## Preferred construction: Let the error propagate.
If the caller cannot handle the error, it should not catch it.
At an external boundary, a specific observed exception may be caught once only to translate it into a typed domain outcome; ordinary callers dispatch that outcome explicitly.

```python
# ## Preferred construction: propagate
data = read_file(path)  # raises if file is missing or unreadable

# When absence is an expected domain state: represent and dispatch it explicitly
match load_config(path):
    case ConfigLoaded(config):
        use_config(config)
    case ConfigAbsent():
        create_initial_config(path)
```

## Use this pattern when:
- The try block wraps a single operation (not a sequence where partial failure is meaningful).
- The catch clause is broad (`Exception`, bare `except`, or a type that does not match the recoverable error).
- Recovery produces a sentinel value (`None`, `[]`, `""`, `False`) distinct from real results.
