# Exception-Driven Ordinary Control Flow

> **Style card `EXPLICIT-STATE-MODEL`.** Load this before designing the relevant boundary. After a policy finding, use the same card to replace the bad shape and prove the preferred construction.

## Bad pattern: Exceptions, failed attempts, or retry order select expected application behavior. The code learns the current state by provoking failure instead of representing the state, its legal transitions, and the operation's preconditions.

```python
# BAD: catch order is the hidden state machine
try:
    execute_transfer(account, transfer)
except VerificationRequired:
    request_verification(account)
except SuspendedAccount:
    reject_transfer(transfer)
```

## Preferred construction: Name every expected state or outcome, validate the transition before effects execute, and dispatch exhaustively. The ordinary path must remain visible at the call site.

```python
# ## Preferred construction: expected states are explicit domain data
match account.state:
    case Unverified():
        request_verification(account)
    case Active():
        execute_transfer(account, transfer)
    case Suspended():
        reject_transfer(transfer)
```

For operations that may be retried, return or translate once into a typed outcome. A retry policy may receive only a classified transient failure. It must require a bounded attempt count, explicit backoff, observability for every attempt, and proof that repeating the operation is safe through transaction semantics or an idempotency key. Permanent rejection, invalid input, invariant failure, and unknown exceptions never enter the retry path.

Use [Error Handling as Control Flow](../../policy-index/references/error-handling-as-control-flow.md) for the canonical rationale and the full list of displaced patterns.

## Use this pattern when:
- catch clauses represent expected business states, validation results, protocol alternatives, or object capabilities;
- code tries operations in sequence until one does not throw;
- failure order changes ordinary behavior;
- retry begins before the failure is classified as transient;
- an effect can partially succeed before another speculative attempt begins.

The remediation is incomplete until the state model names the valid variants, transition ownership is explicit, effect safety is proved, and tests construct domain states directly instead of forcing catch branches.
