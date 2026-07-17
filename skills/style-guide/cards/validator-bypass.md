# Validator Bypass Markers

> **Style card `VALIDATOR-BYPASS`.** Load this before designing the relevant boundary. After a policy finding, use the same card to replace the bad shape and prove the preferred construction.

## Bad pattern: A comment, annotation, or config suppresses a validator (linter, type checker, test requirement) without fixing the underlying issue, converting validator failure into silent acceptance.

```python
# BAD: bypass comment
# type: ignore  # no explanation of why
# pylint: disable=unused-argument  # used in template expansion but linter can't see it
```

## Preferred construction: Either fix the code to satisfy the validator, or escalate the decision.
If the validator is wrong (false positive), document the reason in a durable, specific comment and keep the suppression narrow.
If the validator is right, fix the code.
A bypass comment with no rationale is equivalent to silencing a diagnostic without addressing it.

## Use this pattern when:
- The suppression covers more than one specific line (broad suppression that silences multiple diagnostics).
- The suppression has no comment explaining why the validator is wrong.
- The suppression is in project-owned code (not vendored or generated).

## Choose a different pattern when:
- The suppression targets a known false positive with a documented upstream bug link.
- The suppression is temporary and tracked by an active issue.
