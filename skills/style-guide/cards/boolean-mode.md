# Boolean Mode Parameters

> **Style card `BOOLEAN-MODE`.** Load this before designing the relevant boundary. After a policy finding, use the same card to replace the bad shape and prove the preferred construction.

## Bad pattern: A function takes a boolean parameter that changes its behavior between two modes, forcing callers to read the function body to understand what each value means.

```python
# BAD: boolean mode flag
process_data(data, validate=True)   # what does False mean?
send_notification(user, urgent=False)  # which behavior is default?
```

## Preferred construction: Split into separate functions with descriptive names, or use an explicit enum where each variant name describes the mode.

```python
# ## Preferred construction: split API
process_data_with_validation(data)
process_data_fast(data)

# ## Preferred construction: explicit enum
NotificationPriority = enum(ROUTINE, URGENT)
send_notification(user, NotificationPriority.URGENT)
```

## Use this pattern when:
- The boolean controls which code path is taken (not just a simple toggle of a single behavior like `verbose`).
- The meaning of `True` vs `False` is not obvious from the function name alone.

## Choose a different pattern when:
- The flag is a simple pass-through to a well-known standard library or external API that uses the same convention.
