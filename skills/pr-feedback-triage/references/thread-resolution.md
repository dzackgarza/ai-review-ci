# Verify, Reply, and Resolve Each Feedback Item

Role A verifies C's work against the spec and actual diff.
Green tests are a precondition, not the judgment.

## Verification gate

Record an explicit answer to each question:

1. Did the change solve the first-principles spec rather than the cited symptom?
2. Is the original proof burden discharged at the owned boundary?
3. Did the diff introduce any banned pattern from the governing policy/card?
4. Would each new proof fail on a plausible broken implementation?
5. Does any branch fail open or return partial success?
6. Was anything deleted without burden disposition?
7. Does the declared remediation match the implementation actually being committed?
8. Does the result depend on the reviewer's wording?

Reject failed verification and correct the spec or assign fresh remediation.
Do not patch C's output locally to clear the thread.

## Commit before positive disposition

Commit accepted remediation before replying.
The commit and its proof must exist before the words “accepted,” “fixed,” or “addressed” appear on the thread.
The deterministic gate verifies that the cited SHA belongs to the current PR and that the audit anchor names an existing checkout file, a unique PR commit, or a checkable source/run URL. A syntactically valid SHA or free-form proof sentence is not evidence.
A plan, issue, uncommitted diff, launched agent, or future promise cannot close accepted feedback.

## Canonical thread-local reply contract

Post the reply on the finding's own thread or comment surface.
The field names below are the deterministic gate contract.

Accepted or accepted-with-modification:

```text
Disposition: Accepted as written
Policy basis: POLICY.<CODE>
Pre-filter: <gate and result>
Claim: <first-principles concern>
Remediation: <policy-aligned preferred pattern>
Code/action taken or explicit non-change: <landed change>
Proof: <owned-boundary witness>
Commit: <7-40 hex SHA from the current PR>
Audit anchor: <existing file/test, unique PR commit, or source/run URL>
Deleted artifact: None
```

Use `Disposition: Accepted with modified remediation` when the reviewer's proposed fix was rejected.
The remediation field describes only the policy-aligned implementation.

When no policy governs, replace `Policy basis:` with:

```text
Factual/contract basis: <specific sourced fact or PR-contract clause>
```

Rejected:

```text
Disposition: Rejected
Policy basis: POLICY.<CODE>
Pre-filter: <gate and result>
Claim: <what was evaluated>
Code/action taken or explicit non-change: No code change. <why>
Audit anchor: <source that defeats the claim>
```

Use `Factual/contract basis:` instead when the rejection is purely factual or contractual.
A generic “stale,” “already handled,” or “not warranted” is not evidence.

Duplicate:

```text
Disposition: Duplicate
Policy basis: POLICY.<CODE>
Pre-filter: Same semantic finding -> inherit canonical disposition
Claim: <the concern inherited from the canonical thread>
Canonical thread: <thread URL or stable ID>
Code/action taken or explicit non-change: No additional code change. <inherited disposition>
Audit anchor: <canonical thread>
```

Outdated:

```text
Disposition: Outdated
Policy basis: POLICY.<CODE>
Pre-filter: Finding targets replaced code -> superseded
Claim: <the concern that no longer applies>
Superseding commit: <7-40 hex SHA>
Code/action taken or explicit non-change: No additional code change. <why the concern no longer applies>
Audit anchor: <superseding diff or proof>
```

Backlogged minor debt:

```text
Disposition: Backlogged as minor technical debt
Factual/contract basis: <localized debt evidence and why current-PR criteria do not trigger>
Pre-filter: Gate 3 current-PR obligations absent -> backlogged minor debt
Claim: <the localized maintainability concern>
Debt issue: https://github.com/<owner>/<repo>/issues/<number>
Code/action taken or explicit non-change: No current-PR code change.
Audit anchor: <source plus debt issue>
```

Investigation required:

```text
Disposition: Investigate before action
Policy basis: POLICY.<CODE>
Pre-filter: <gate and unresolved evidence result>
Claim: <the claim whose truth is not yet established>
Evidence gap: <specific missing fact>
Next evidence required: <observation that would decide or falsify the claim>
Code/action taken or explicit non-change: No code change while the evidence gap remains open.
Audit anchor: <current source or runtime evidence>
```

Use `Factual/contract basis:` instead when no policy governs.
Post or update this reply on the finding's own surface, then keep the item open and route it through [[pr-feedback-triage/references/investigation|the evidence-gathering loop]].

When replacing an incomplete or investigative canonical reply, edit that same reply into the final contract when the active identity can do so.
If a corrective reply already exists, the collector selects the latest complete canonical reply; otherwise it resumes from the latest incomplete reply.
Do not append duplicates merely to avoid editing, but do not let an earlier malformed reply hide a later valid correction.

## Deletion appendix

When remediation deletes an artifact, append:

```text
Deleted artifact: <file or object>
Original burden: <what it attempted to solve or prove>
Burden disposition: <solved by | invalidated by | transferred to | remains open in> <owned evidence or blocker>
Verification: <witness>
```

Replace `Deleted artifact: None` with the deletion appendix whenever accepted remediation removes an artifact.
The gate requires exactly one of the burden-disposition verbs above and a verification witness; do not claim “removed” as resolution.

## Surface-specific completion

“Resolve” is not one operation:

| Feedback object | Required visible completion |
| --- | --- |
| Inline review thread | Canonical reply on the thread, then resolve the thread through GitHub |
| Top-level PR comment | Reply on that comment surface; it has no thread-resolution bit |
| Formal review summary | Reply on the PR comment surface and address each substantive item |
| Check annotation or failed check | Correct the owned failure and let the check rerun; do not pretend thread resolution clears it |
| Linked GitHub issue | Update, comment on, or close the issue itself; PR-thread resolution does not change issue state |

## Resolution

Only after the visible reply exists should A resolve an inline thread through GitHub.
The resolve mutation's justification is not visible thread evidence.
Top-level comments, review summaries, check annotations, and linked issues have distinct surfaces; reply or update the object itself rather than pretending GraphQL thread resolution clears it.

The thread-local reply is the canonical audit record.
Do not duplicate it into a top-level disposition ledger or tracked review-log file.
