# justfile-qc-tooling — QC profile for repos whose product *is* QC infrastructure.
#
# ai-review-ci ships the opinionated slop/style/duplication gates (semgrep,
# ast-grep, jscpd, vibecheck, ai-slop) for *downstream product code*. Applying
# them to this repo's own infrastructure is the wrong shape — the long-standing
# "skip ai-review-ci QC on itself" carve-out.
#
# But "skip slop rules" must not mean "no CI". QC is a repo running its own
# standardized three-tier recipes against itself. This profile is that
# standard minus the product-only gates: it reuses python.just's correctness
# subrecipes (project-shape, normalize, syntax, mypy, pytest, changed-line
# coverage, deptry, import-linter) and omits semgrep / ast-grep / jscpd /
# vibecheck / slop. Reusing the subrecipes (rather than re-spelling them) keeps
# this profile from duplicating python.just.
#
# A repo selects it the same way as any other profile:
#   just -f ~/ai-review-ci/justfiles/qc-tooling.just -d . test-commit
#
# WORKFLOW (three-tier, matching every other profile):
#   just test-commit — normalize, syntax, and mypy.
#   just test-push   — commit checks plus pytest.
#   just test-ci     — push checks plus coverage, deptry, and import-linter.

infra := justfile_directory() / ".."
justfiles := infra / "justfiles"

# Correctness subrecipes run in one python.just invocation so the shared
# `_install-tools` dependency resolves once.
#
# NB: python.just's `_check-python-project` preflight is deliberately omitted —
# it enforces *downstream-consumer* shape (no local QC tool configs, a specific
# test layout) that is inverted for the QC owner: ai-review-ci legitimately owns
# the tool configs it ships. Correctness is still proven by mypy + pytest (which
# fail if types are wrong or tests are absent/failing).
_commit-recipes := "_normalize _python-syntax _mypy"
_push-recipes := "_pytest"
_ci-recipes := "_pytest_with_coverage _diff-cover _deptry _import-linter"

# public: COMMIT gate — immediate, directly repairable feedback
test-commit:
    #!/usr/bin/env bash
    set -euo pipefail
    export AI_REVIEW_CI_FAILURE_MODE=direct
    just --justfile {{infra}}/justfile -d . check
    uv run --project {{infra}} ai-review-ci check-tripwire-index
    just -f {{justfiles}}/python.just -d . {{_commit-recipes}}
    just -f {{justfiles}}/shared.just -d . _no-bypass
    echo "QC-tooling commit checks completed"

# public: PUSH gate — commit checks plus the full project-owned test suite
test-push:
    #!/usr/bin/env bash
    set -euo pipefail
    export AI_REVIEW_CI_FAILURE_MODE=direct
    just --justfile {{justfile()}} -d . test-commit
    just -f {{justfiles}}/python.just -d . {{_push-recipes}}
    echo "QC-tooling push checks completed"

# public: CI gate — push checks plus coverage/dependency/import gates, no slop
test-ci:
    #!/usr/bin/env bash
    set -euo pipefail
    export AI_REVIEW_CI_FAILURE_MODE=triage
    just --justfile {{infra}}/justfile -d . check
    just --justfile {{justfile()}} -d . test-push
    just -f {{justfiles}}/python.just -d . {{_ci-recipes}}
    echo "QC-tooling CI checks completed"

# Scheduled, NOT in the PR/push gate: pre-existing repo-wide debt stays visible
# and reviewable without blocking unrelated PRs (#53), and is the non-blocking
# debt surface (#55) — no baseline/quarantine file silences anything; findings
# are reviewed and tracked as issues.
#
# public: AMBIENT audit — full-repo deferred-debt scan (complexity, dead code, duplication)
ambient:
    #!/usr/bin/env bash
    set -euo pipefail
    export AI_REVIEW_CI_FAILURE_MODE=triage
    just -f {{justfiles}}/python.just -d . _ambient-python-debt
    echo "QC-tooling ambient debt audit completed"
