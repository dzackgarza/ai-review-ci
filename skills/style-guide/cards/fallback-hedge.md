# Fallback / Optional-Dependency / File-Availability Hedge

> **Style card `FALLBACK-HEDGE`.** Load this before designing the relevant boundary. After a policy finding, use the same card to replace the bad shape and prove the preferred construction.

## Bad pattern: A guard checks whether a dependency, file, binary, or resource exists before using it, with a silent fallback when absent.

```python
# BAD: silent hedge
if shutil.which("ffmpeg"):
    subprocess.run(["ffmpeg", ...])
else:
    logger.warning("ffmpeg not found, skipping")

# BAD: optional critical dependency
try:
    import magic
except ImportError:
    magic = None
```

## Preferred construction: Assert availability at the program boundary.
If the resource is required, failure to find it is a hard error.
Do not provide a silent branch.

```python
# ## Preferred construction: boundary assertion
assert shutil.which("ffmpeg"), "ffmpeg is required for video processing"
subprocess.run(["ffmpeg", ...])
```

## Use this pattern when:
- The dependency, file, or binary is required for the operation being performed.
- The app controls deployment (it can guarantee the dependency is present).
- The only purpose of the guard is to avoid an error that would be correct to raise.

## Choose a different pattern when:
- The app legitimately supports multiple optional backends chosen by config.
- The resource is genuinely external and its absence is a valid runtime condition (e.g., network availability for a cache).
