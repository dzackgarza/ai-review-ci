# Nested / Stacked Conditional Chains

> **Style card `NESTED-CONDITIONAL`.** Load this before designing the relevant boundary. After a policy finding, use the same card to replace the bad shape and prove the preferred construction.

## Bad pattern: A cascade of `if`/`elif`/`else` that branches on a single discriminant (type, enum, status, state) with implicit fall-through for unhandled cases.

```python
# BAD: stacked if/elif chain with implicit unhandled cases
if event.type == "click":
    handle_click(event)
elif event.type == "focus":
    handle_focus(event)
elif event.type == "blur":
    handle_blur(event)
# other event types silently ignored
```

## Preferred construction: Use a match/case (Python 3.10+, TypeScript, Rust, etc.) or an explicit dispatch table that enumerates all expected cases and fails hard on unexpected input.

```python
# Remediation (match/case): explicit, exhaustive, fails on unexpected
match event.type:
    case "click": handle_click(event)
    case "focus": handle_focus(event)
    case "blur":  handle_blur(event)
    case _:       raise ValueError(f"unexpected event type: {event.type}")

# Remediation (dispatch table): equally explicit
_HANDLERS = {
    "click": handle_click,
    "focus": handle_focus,
    "blur":  handle_blur,
}
handler = _HANDLERS.get(event.type)
assert handler is not None, f"unexpected event type: {event.type}"
handler(event)
```

## Use this pattern when:
- The chain is 3+ branches on the same discriminant.
- The default/else branch is missing, empty, or just logs and continues.
- The discriminant is a bounded set (enum, string literal union, known type variants).
