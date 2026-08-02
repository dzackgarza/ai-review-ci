# `if`/`else`/`elif` Where Exhaustive Match Belongs

> **Style card `EXHAUSTIVE-DISPATCH`.** Load this before designing a branch over cases. After a policy finding, use the same card to replace the bad shape and prove the preferred construction.

Policy: `POLICY.NO_IF_ELSE`

## Bad pattern: A discriminator is branched with `if`/`else`/`elif` instead of an exhaustive `match`/`case` over a typed enum or tagged union. Non-coverage is invisible; a missing case silently falls through to `else` (or to nothing). A default arm that returns a default, empty, or falsy value is a laundered `else`.

```python
# BAD: elif ladder over a discriminator; missing case falls into else unnoticed
def handle_event(event: Event) -> Result:
    if event.kind == "created":
        return handle_created(event)
    elif event.kind == "updated":
        return handle_updated(event)
    elif event.kind == "deleted":
        return handle_deleted(event)
    else:
        return Result.empty()  # laundered fallback; a new EventKind lands here silently
```

```ts
// BAD: default arm returns a default — a renamed else
function render(node: Node): string {
  switch (node.kind) {
    case "text": return node.value;
    case "bold": return `**${render(node.child)}**`;
    default: return "";  // new NodeKind silently renders as empty string
  }
}
```

Why this is wrong here: `if`/`else`/`elif` and non-exhaustive `switch` make non-coverage a silent runtime behavior. The type checker cannot prove every case is handled. Adding a new variant does not produce a compile error at the dispatch site — it falls into `else` or `default`, which by precedent returns a default/empty value, turning an unhandled case into fail-open execution (`POLICY.FAIL_OPEN`, `POLICY.NO_PARTIAL_SUCCESS`). A `default` arm that re-raises is no better: it preserves the branch shape and lets future agents insert recovery, logging, or partial success at the catch-all.

## Preferred construction: Encode the discriminator as an enum or tagged union and dispatch exhaustively. Exhaustiveness is the proof. The `case _` / `default` arm is always written and is always `assert_never` (or language equivalent: `assertNever` in TypeScript, `unreachable!()` in Rust) — never a fallback return, never a generic re-raise, never omitted. It is not optional and does not depend on whether the compiler enforces exhaustiveness; it is the proof obligation made visible at the dispatch site.

Error handling is not a collapse into one generic catch-all. Each domain-known error situation is its own `case` arm raising its own typed error. `case _` is `assert_never` and means *no* case was overlooked — it is not where error handling lives. Error handling lives in named cases that the domain owns.

```python
# ## Preferred construction: exhaustive match; named error cases; case _ is assert_never
from enum import Enum
from typing import assert_never

class EventKind(Enum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    MALFORMED = "malformed"      # domain-known error: payload failed schema
    UNAUTHORIZED = "unauthorized" # domain-known error: caller lacked permission
    CONFLICT = "conflict"         # domain-known error: stale version

class MalformedEventError(Exception): ...
class UnauthorizedEventError(Exception): ...
class EventConflictError(Exception): ...

def handle_event(event: Event) -> Result:
    match event.kind:
        case EventKind.CREATED:
            return handle_created(event)
        case EventKind.UPDATED:
            return handle_updated(event)
        case EventKind.DELETED:
            return handle_deleted(event)
        case EventKind.MALFORMED:
            raise MalformedEventError(
                f"event payload failed schema; event_id={event.id}; "
                f"schema={EVENT_SCHEMA_VERSION}; "
                "fix the producer or the schema in schemas/event.json"
            )
        case EventKind.UNAUTHORIZED:
            raise UnauthorizedEventError(
                f"caller lacks permission for event; event_id={event.id}; "
                f"caller={event.caller_id}; "
                "grant the caller the required role or fix the caller"
            )
        case EventKind.CONFLICT:
            raise EventConflictError(
                f"stale version on event; event_id={event.id}; "
                f"expected={event.expected_version}; found={event.version}; "
                "re-fetch the current version and retry, or report the conflict upstream"
            )
        case _:
            assert_never(event.kind)  # an EventKind the domain does not own yet
```

```ts
// ## Preferred construction: discriminated union; named error cases; default is assertNever
type Node =
  | { kind: "text"; value: string }
  | { kind: "bold"; child: Node }
  | { kind: "malformed"; reason: string; raw: unknown }
  | { kind: "unauthorized"; caller: string; requiredRole: string };

class MalformedNodeError extends Error { ... }
class UnauthorizedNodeError extends Error { ... }

function assertNever(value: never): never {
  throw new AssertionError(`unhandled variant: ${JSON.stringify(value)}`);
}

function render(node: Node): string {
  switch (node.kind) {
    case "text": return node.value;
    case "bold": return `**${render(node.child)}**`;
    case "malformed":
      throw new MalformedNodeError(
        `node payload failed schema; reason=${node.reason}; ` +
        `raw=${JSON.stringify(node.raw)}; fix the producer or the node schema`
      );
    case "unauthorized":
      throw new UnauthorizedNodeError(
        `caller lacks permission; caller=${node.caller}; ` +
        `requiredRole=${node.requiredRole}; grant the role or fix the caller`
      );
    default: return assertNever(node);
  }
}
```

```rust
// ## Preferred construction: the compiler proves coverage; named error variants
// The catch-all arm is always written and is unreachable!() with the variant
// in the message — the assert_never analogue. It is not omitted because the
// compiler checks coverage; the proof belongs in the code. Error variants are
// named arms returning typed Err values, not a collapse into a generic catch-all.
fn handle_event(event: &Event) -> Result<Response, EventError> {
    match event.kind {
        EventKind::Created => Ok(handle_created(event)?),
        EventKind::Updated => Ok(handle_updated(event)?),
        EventKind::Deleted => Ok(handle_deleted(event)?),
        EventKind::Malformed => Err(EventError::Malformed {
            event_id: event.id,
            schema: EVENT_SCHEMA_VERSION,
            reason: event.reason.clone(),
            fix: "fix the producer or the schema in schemas/event.json",
        }),
        EventKind::Unauthorized => Err(EventError::Unauthorized {
            event_id: event.id,
            caller_id: event.caller_id,
            fix: "grant the caller the required role or fix the caller",
        }),
        EventKind::Conflict => Err(EventError::Conflict {
            event_id: event.id,
            expected_version: event.expected_version,
            found_version: event.version,
            fix: "re-fetch the current version and retry, or report the conflict upstream",
        }),
        _ => unreachable!(
            "unhandled EventKind: {:?}; known variants: Created, Updated, Deleted, Malformed, Unauthorized, Conflict; add a case arm or narrow the enum",
            event.kind
        ),
    }
}
```

The `case _` / `default` arm is mandatory. It is `assert_never` (or language equivalent) — a proof that the listed cases are total, made visible at every dispatch site regardless of whether the language's compiler independently enforces exhaustiveness. A `case _` arm that returns a value, re-raises generically, logs, or falls through is a laundered `else` and is banned. Omitting the arm because "the compiler checks it" is also banned: the proof belongs in the code, not in an external tool's behavior.

### Invariant branches are not cases

If a branch checks an invariant rather than a domain case, it is not dispatch — it is proof. Use an assertion. Do not encode `if x is not None` as a one-armed `match` to satisfy this policy; that is `POLICY.PREFER_ASSERTION` / `POLICY.TOTAL_CORE_STATE`.

```python
# BAD: using match to enforce an invariant
match state.current_document:
    case None:
        raise AssertionError("current_document must be initialized")
    case doc:
        return render(doc)

# ## Preferred construction: assert the invariant, proceed linearly
assert state.current_document is not None, "current_document must be initialized"
return render(state.current_document)
```

### Languages without a typed exhaustive dispatch primitive

Where the language has no `match` with exhaustiveness checking, the obligation still holds. Model the cases as variants and dispatch via a total function whose non-coverage is either a compile error (generated dispatch, function-table keyed by variant) or a fail-loud runtime assertion that names the missing variant. A silent default return is banned under both this policy and `POLICY.FAIL_OPEN`.

```python
# ## Preferred construction (no native exhaustive match): function table + fail-loud default
_HANDLERS: dict[EventKind, Callable[[Event], Result]] = {
    EventKind.CREATED: handle_created,
    EventKind.UPDATED: handle_updated,
    EventKind.DELETED: handle_deleted,
}

def handle_event(event: Event) -> Result:
    handler = _HANDLERS.get(event.kind)
    assert handler is not None, (
        f"unhandled EventKind; found={event.kind}; "
        f"known={[k.value for k in EventKind]}; "
        "add a handler in _HANDLERS or narrow the EventKind enum"
    )
    return handler(event)
```

The fail-loud default is an assertion, not a fallback: it names the missing variant and directs the maintainer to the dispatch table. It must not return a default result.

## Choose a different pattern when:
- The branch is an invariant, not a domain case — use `ASSERT-OVER-RAISE`, not this card.
- The branch guards a boundary parser rejecting external input — `POLICY.FAIL_LOUD_BOUNDARY` owns that; a single boundary `if`/raise-shaped check is admissible there, not here.
- The branch is a domain predicate filtering/partitioning data where both outcomes are valid — exhaustive dispatch over an enum is not required; the partition is the domain operation (see `runtime-control-flow.md` Allowed branches).

## Proof obligations
- The dispatch is exhaustive: the type checker proves coverage, or the runtime assertion names every missing variant.
- No default arm returns a default, empty, falsy, or re-raised value.
- The `case _` / `default` arm is always written and is always `assert_never` (or language equivalent) — never a fallback return, generic re-raise, log, fallthrough, or omitted on the grounds that the compiler enforces coverage.
- No `if`/`else`/`elif` remains in the same function over the same discriminator after remediation.
- Invariant branches are assertions, not `match` arms.
- Tests construct each variant directly and assert per-variant semantic behavior, not a shared default.