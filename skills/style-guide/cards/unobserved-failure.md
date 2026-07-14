# Unobserved-Failure Branches

> **Style card `UNOBSERVED-FAILURE`.** Load this before designing the relevant boundary. After a policy finding, use the same card to replace the bad shape and prove the preferred construction.

## Bad pattern: Code that handles a failure case, edge condition, or error path that has never been observed in practice — branching on an event the author hypothesizes might happen rather than one demonstrated by a real failure.

```python
# BAD: branch for a failure never observed
try:
    data = api.fetch()
except TimeoutError:
    data = None  # API calls have never timed out in this environment
```

## Preferred construction: Do not add handling for failure modes that have not been observed.
If the condition is logically impossible (invariant already guaranteed upstream), assert rather than branch.
When a failure IS observed, add targeted handling for that specific case.

```python
# ## Preferred construction: assert the invariant
data = api.fetch()  # raises if network fails — correct behavior

# When the invariant is guaranteed by the caller:
assert data is not None, "upstream guarantees api.fetch returns data"
process(data)
```

## Use this pattern when:
- The failure branch has no corresponding test that reproduces it.
- The handler produces a sentinel or silent continuation.
- The condition is logically impossible given upstream invariants.

## Choose a different pattern when:
- The failure is well-known in the domain and occurs regularly (e.g., network timeout on HTTP calls to external services).
- The handling is required by the API contract (e.g., an interface method that must handle all enum variants).
