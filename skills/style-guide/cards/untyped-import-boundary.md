# Untyped Third-Party Imports

> **Style card `UNTYPED-IMPORT-BOUNDARY`.** Load this before designing the relevant boundary. After a policy finding, use the same card to replace the bad shape and prove the preferred construction.

## Bad pattern: A mypy `import-untyped` diagnostic appears because a dependency lacks stubs or a `py.typed` marker.
The agent treats the diagnostic as a reason to change the dependency, hand-roll the feature, suppress mypy, or scatter casts.

```python
# BAD: direct untyped import in product code
from untyped_yaml import load

payload = load(text)
```

```toml
# BAD: local validator silence
[[tool.mypy.overrides]]
module = ["untyped_yaml.*"]
ignore_missing_imports = true
```

Remediation order:

- Preserve the correct library unless product requirements independently reject it.
  Do not replace a library solely because it is untyped.
- If maintained stubs exist, add the stub package through the approved dependency path.
  Generic reusable stubs belong in global QC/tooling; repo-specific runtime or test stubs belong in the repo only when they are part of the project’s declared dependency surface.
- If no maintained stubs exist and the needed API is small, add minimal `.pyi` stubs for the exact imported module and symbols.
  Stub only the surface the project uses.
- If stubbing would be large or brittle, isolate the untyped import in one typed firewall module.
  The firewall imports the untyped library, validates or converts its outputs, and returns project-owned named types.
  Owned code imports the firewall, not the untyped library.
- Global QC should provide the only allowed `import-untyped` carve-out: firewall modules may be exempt from that specific diagnostic, while direct imports elsewhere remain blockers.

Firewall shape:

```python
# src/project/_type_firewalls/untyped_yaml.py
from dataclasses import dataclass

from untyped_yaml import load


@dataclass(frozen=True)
class ParsedConfig:
    command: str
    timeout_ms: int


def parse_config(text: str) -> ParsedConfig:
    raw = load(text)
    assert isinstance(raw, dict), "config must parse to a mapping"
    command = raw["command"]
    timeout_ms = raw["timeout_ms"]
    assert isinstance(command, str), "command must be a string"
    assert isinstance(timeout_ms, int), "timeout_ms must be an integer"
    return ParsedConfig(command=command, timeout_ms=timeout_ms)
```

Firewall constraints:
- exactly one module imports the untyped dependency;
- no untyped dependency objects cross the firewall boundary;
- the firewall returns named project-owned types, not `dict[str, object]`, `Any`, or library-native objects;
- downstream code has no `Any`, casts, or mypy ignores for the dependency;
- semantic tests exercise the project boundary that consumes the typed result.

Canonical exclusion rule: global QC may ignore `import-untyped` only for modules under the project’s type-firewall convention, such as `src/<package>/_type_firewalls/<dependency>.py`. The same gate must still reject the untyped import outside that convention.
Repo-local mypy config, file-level ignore comments, and blanket `ignore_missing_imports` remain validator bypasses.

## Use this pattern when:
- mypy reports `import-untyped`, `missing library stubs`, or missing `py.typed`;
- the dependency is otherwise the correct library for the job;
- owned code would receive `Any` from that import.

## Choose a different pattern when:
- the library is wrong for product reasons unrelated to type checking;
- a typed first-party API or official replacement is already the documented successor;
- the import is unused and can be deleted without changing the intended capability.

<a id="remediation-boundary-test-bypass"></a>
