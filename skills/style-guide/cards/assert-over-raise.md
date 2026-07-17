# `if/raise` Where an Assertion Belongs

> **Style card `ASSERT-OVER-RAISE`.** Load this before designing the relevant boundary. After a policy finding, use the same card to replace the bad shape and prove the preferred construction.

Policy: `POLICY.PREFER_ASSERTION`, `POLICY.NO_HYPOTHETICAL_PATH`

## Bad pattern: An invariant or precondition is enforced with `if not cond: raise ValueError(...)`/`RuntimeError(...)` instead of `assert cond, "..."`, or an existing assertion is wrapped in `try/except AssertionError`. The most common trigger is a reviewer (often an automated one) recommending "replace `assert` with `if/raise` because assertions are stripped under `python -O`." Accepting that recommendation is the slop.
Catching assertion failure is the same slop in catch-form: it turns a provable claim about state into runtime logic.

```python
# BAD: if/raise on what is an invariant, "to survive python -O"
def global_vault_path() -> Path:
    override = os.environ.get("AGENT_MEMORY_VAULT")
    if override is not None:
        if not override.strip():
            raise ValueError("AGENT_MEMORY_VAULT must not be empty when set")
        return Path(override).expanduser()
    ...

# BAD: catching an assertion turns proof into runtime behavior
def run_with_config(config: RuntimeConfig) -> None:
    try:
        assert config.command, "runtime command is required"
    except AssertionError:
        repair_or_continue()
    run(config.command)
```

Why this is wrong here: Assertions are the strongly-preferred idiom.
An `assert` is an auditable proof of what the author believes must be true at that point; it forces the writer to engage with the data, name real failure modes, and narrow types so the checker can validate the branch.
`if/raise` on an invariant is adjacent to timid, fail-open, splat-guessing slop and removes that proof.
The `python -O` argument is hypothetical fiction (`POLICY.NO_HYPOTHETICAL_PATH`): these are bespoke tools that are never run with `-O`, the assertion-stripping failure has never been observed, and protecting downstream users who pass optimization flags is not an owned obligation.

```python
# ## Preferred construction: keep the assertion; if anything, make it stronger
def global_vault_path() -> Path:
    override = os.environ.get("AGENT_MEMORY_VAULT")
    if override is not None:
        assert override.strip(), (
            "AGENT_MEMORY_VAULT must name a path when set; "
            "config source=environment; "
            "fix ~/.envrc or unset the variable before running agent-memory"
        )
        return Path(override).expanduser()
    ...
```

## Preferred construction: Reject the suggestion.
Restore (or keep) the `assert`. Then audit the assertion itself: is it the strongest provably-true statement available at that point, does it dump the related data needed to repair the failure, and does it direct the maintainer to the owning config, data file, command, usage surface, or owned tool repository?
Strengthen it if a more precise invariant or more useful ADDD payload holds.
Do not add a raise-based escape hatch or a catch-based recovery path.

## Choose a different pattern when:
- The raise is a genuine domain error on observed external input the app contractually owns (see `[STRINGLY-ERROR]` for using structured error types there) — not an internal invariant.
- The boundary is an approved error-translation renderer turning a structured internal error into a user-facing protocol (see `test-guidelines` Try/Catch Ban exception).
