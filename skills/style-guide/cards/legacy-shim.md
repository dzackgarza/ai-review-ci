# Compatibility / Legacy Shims

> **Style card `LEGACY-SHIM`.** Load this before designing the relevant boundary. After a policy finding, use the same card to replace the bad shape and prove the preferred construction.

## Bad pattern: Wrappers, adapters, deprecated-function stubs, or feature flags that preserve a wrong earlier interface alongside the replacement — keeping dead code alive and multiplying the surface area that must be maintained and reviewed.

```python
# BAD: keeps old interface alive
def old_api(x, y):
    return new_api(x=x, y=y)
old_api.__doc__ = "Deprecated: use new_api instead"
```

## Preferred construction: Replace the callers, then delete the old interface.
In pre-launch code there are no legacy consumers — every shim is dead weight that doubles the review surface and preserves wrong patterns that future code will copy.

## Use this pattern when:
- The shim exists "for compatibility" in pre-launch code with no known callers outside the repo.
- The old interface is worse (wrong names, wrong types, wrong defaults) and the replacement is complete.
- A deprecation warning or docstring is used instead of deleting the old code.

## Choose a different pattern when:
- The old interface has external consumers outside the repo (published library, public API).
- Migration requires coordinated changes across multiple repos and the shim is temporary with an owner and deadline.
