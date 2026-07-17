Error handling as routine control flow replaces knowledge with collision. The program does not represent what states exist, which transitions are legal, or why an operation should succeed. It blindly performs operations until the runtime rejects enough of them to stumble onto an acceptable path.

That is the lemmings-across-a-chasm model: instead of constructing a bridge from known constraints, repeatedly throw attempts into failure and treat the first survivor as the algorithm.

### Short-term damage

It appears expedient because the programmer avoids modeling the problem. Instead of determining the current state and selecting the valid operation, they write:

```text
try A
catch: try B
catch: repair something and retry A
catch: use C
```

This saves thought and perhaps a few lines initially, but immediately creates:

- Multiple expensive attempts instead of one justified operation.
- Partial mutations that must somehow be detected or undone.
- Ambiguity about whether failure means “wrong state,” “invalid input,” “temporary outage,” “programming defect,” or “corrupted data.”
- Logs full of expected exceptions, concealing real failures.
- Debugging that depends on reconstructing which attempts happened before the survivor.
- Tests coupled to incidental exception order rather than domain behavior.
- Latency, resource waste, rate-limit pressure, and duplicated side effects.

The runtime becomes an oracle answering questions the program should already know how to answer.

### Long-term damage

The accidental retry tree gradually becomes the de facto domain model—but an implicit, incomplete, and distributed one. Every new case adds another catch, fallback, or retry. Because no authoritative state model exists, later programmers cannot safely remove any branch: each may encode some undocumented production condition.

Eventually:

- Failure order becomes part of the application’s behavior.
- Infrastructure errors become indistinguishable from business decisions.
- New exception types silently change control flow.
- Broad catches swallow defects and invariant violations.
- Retries duplicate payments, messages, writes, or external requests.
- Non-idempotent operations corrupt state.
- Recovery paths receive less testing than normal paths while effectively becoming normal paths.
- Performance and correctness depend on undocumented timing.
- Observability reports a system that is constantly “failing” even when behaving as designed.
- Genuine incidents disappear into the noise of deliberately generated failures.

The code becomes resistant to understanding because behavior is defined negatively: not by what must happen, but by the sequence of things that happened not to work.

### Why readability collapses

Readable code states its decision:

```text
match account.state:
    Unverified => request_verification()
    Active     => execute_transfer()
    Suspended  => reject_transfer()
```

Exception-driven code hides that decision:

```text
try execute_transfer()
catch VerificationRequired: request_verification()
catch SuspendedAccount: reject_transfer()
catch TransferFailed: ...
```

The reader must inspect every callee to discover what might be thrown, determine which exceptions are expected, understand catch precedence, track mutations performed before unwinding, and infer which failures represent domain states. The nominal “happy path” is therefore a lie: the catches contain ordinary behavior, while the `try` block pretends the operation was expected to succeed.

Control flow is no longer locally visible. It depends on invisible, non-local exits from arbitrary stack depth.

### Why it belies domain understanding

A competent implementation knows:

- the possible states;
- the legal transitions;
- the preconditions for each operation;
- which failures are permanent;
- which failures are transient;
- what may safely be retried;
- which effects are transactional or idempotent.

Guess-and-check substitutes runtime experimentation for that knowledge. It is “braindead” in the precise control-theoretic sense: it acts without an internal model. Its only intelligence is impact feedback—attempt, collide, recoil, attempt again.

This is physically lazy because it avoids tracing contracts, reading schemas, inspecting state, and writing explicit branches. It is intellectually lazy because it refuses to name the domain concepts and prove that the selected transition is valid. The cost is merely externalized onto machines, logs, operators, users, and future maintainers.

### What it displaces

Routine exceptional control flow crowds out the correct abstractions:

- Sum types such as `Result`, `Option`, and explicit domain outcomes.
- Exhaustive pattern matching.
- State machines with named legal transitions.
- Validation and precondition checks.
- Capability-based APIs that make invalid operations unavailable.
- Transactions and explicit rollback semantics.
- Idempotency keys and deduplication.
- Typed error taxonomies separating domain rejection, programmer defects, and infrastructure failure.
- Bounded retry policies restricted to identified transient failures.
- Protocol negotiation instead of speculative invocation.
- Parsers and validators that report structured alternatives instead of repeatedly crashing.

These patterns make states and decisions inspectable. Guess-and-catch keeps them accidental.

### Why it abuses language semantics

Exceptions are an abnormal stack-unwinding mechanism. They exist to interrupt a computation that cannot fulfill its contract at the current level and transfer responsibility to a boundary capable of recovery. They are not intended to serve as hidden `goto`, polymorphic return values, state probes, or general-purpose branching.

Using them routinely abuses their defining properties—non-local transfer, automatic unwinding, and failure propagation—to avoid expressing ordinary semantics. It converts “this operation cannot continue” into “this is how we normally decide what to do.”

Retries have a legitimate role only after the program has classified a failure as transient, established that retrying is safe, and imposed a bounded policy with backoff and observability. Likewise, a language may deliberately define narrow exception-based protocols. Those are explicit contracts.

The anti-pattern is not merely that exceptions appear. It is that failure is deliberately provoked to discover ordinary control flow because the program lacks—or declines to encode—the knowledge required to choose correctly.
