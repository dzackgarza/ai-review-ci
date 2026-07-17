# Implicit / Defaulted / Discovered State

> **Style card `IMPLICIT-STATE`.** Load this before designing the relevant boundary. After a policy finding, use the same card to replace the bad shape and prove the preferred construction.

## Bad pattern: The app relies on runtime defaults, ambient discovery (inferring config from machine state), hidden global state (shell/env/cache), or optional core state with "maybe initialized" logic — all of which bury configuration in unreviewable surfaces and make behavior depend on ephemeral external conditions.

These are distinct variants of the same failure: state that should be explicit is implicit, discoverable only by reading non-code surfaces.

## Preferred construction: Declare all configuration explicitly in a committed project config file.
Validate the config at startup; fail hard if values are missing or invalid.
Core state is total — normalized once at initialization, never optional.

```
File layout:
  config/app.toml         ← reviewed, diffable, committed
  src/config/loader.py    ← reads app.toml, validates, fails on missing keys
  src/app.py              ← imports config, uses total (non-optional) state
```

## Use this pattern when:
- Behavior changes based on ambient machine state (env vars, home dir, cache presence, installed tools).
- Core app state is `None | T` (optional) when it could be `T` after initialization.
- Configuration values have defaults that hide from explicit review.

## Choose a different pattern when:
- The value is genuinely a runtime choice the user makes per-invocation (e.g., `--output-format json`).
- The ambient state is the domain (e.g., a file manager inspecting the filesystem).
