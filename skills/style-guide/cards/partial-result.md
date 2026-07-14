# Partial / Sentinel Results

> **Style card `PARTIAL-RESULT`.** Load this before designing the relevant boundary. After a policy finding, use the same card to replace the bad shape and prove the preferred construction.

## Bad pattern: An operation that can partially succeed produces a result object with some fields populated and others sentinel (None, empty, -1) — forcing every caller to check which parts are valid.

```python
# BAD: partial success object
result = fetch_data(url)
if result.status == "ok":
    process(result.data)
# else: caller must check every access
```

## Preferred construction: An operation either succeeds completely or fails with a clear error.
Do not return objects that are "mostly OK" with missing parts.
If the operation genuinely has partial results, represent them as explicit alternatives (union type, enum variant, tagged sum).

```python
# ## Preferred construction: complete success or clear failure
data = fetch_data(url)  # raises if any part fails
# or, if partial results are domain-meaningful:
match result:
    case Complete(data=all_data): process(all_data)
    case Partial(data=some_data, missing=ids): handle_missing(ids)
    case Failure(error=err): raise err
```

## Use this pattern when:
- A function returns a result where some fields can be `None`, empty, or otherwise sentinel after partial failure.
- Callers must check sentinel values on every access.
- A single success/failure boolean would be sufficient.

## Choose a different pattern when:
- The domain genuinely models multiple valid outcomes (e.g., a batch job where some items succeed and others fail).
- The sentinel is the domain contract (e.g., `dict.get(key)` returns `None` for missing keys).
