# justfile-qc-tooling — QC profile for repos whose product *is* QC infrastructure.
#
# ai-review-ci ships the opinionated slop/style/duplication gates (semgrep,
# ast-grep, jscpd, vibecheck, ai-slop) for *downstream product code*. Applying
# them to this repo's own infrastructure is the wrong shape — the long-standing
# "skip ai-review-ci QC on itself" carve-out.
#
# But "skip slop rules" must not mean "no CI". QC is a repo running its own
# standardized `test` / `test-ci` recipes against itself. This profile is that
# standard minus the product-only gates: it reuses python.just's correctness
# subrecipes (project-shape, normalize, syntax, mypy, pytest, changed-line
# coverage, deptry, import-linter) and omits semgrep / ast-grep / jscpd /
# vibecheck / slop. Reusing the subrecipes (rather than re-spelling them) keeps
# this profile from duplicating python.just.
#
# A repo selects it the same way as any other profile:
#   just -f ~/ai-review-ci/justfiles/qc-tooling.just -d . test
#
# WORKFLOW (two-tier, matching every other profile):
#   just test     — COMMIT gate: preflight, normalize, syntax, mypy, pytest.
#   just test-ci  — PUSH/CI gate: + changed-line coverage, deptry, import-linter.

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
_commit-recipes := "_normalize _python-syntax _mypy _pytest"
_ci-recipes := "_pytest_with_coverage _diff-cover _deptry _import-linter"

# public: COMMIT gate — correctness + normalization only (no slop/style gates)
test:
    #!/usr/bin/env bash
    set -euo pipefail
    just --justfile {{infra}}/justfile -d . check
    just -f {{justfiles}}/python.just -d . {{_commit-recipes}}
    just -f {{justfiles}}/shared.just -d . _no-bypass
    echo "QC-tooling commit-tier checks completed"

# public: PUSH/CI gate — correctness + coverage/dependency/import gates, no slop
test-ci:
    #!/usr/bin/env bash
    set -euo pipefail
    just --justfile {{infra}}/justfile -d . check
    just -f {{justfiles}}/python.just -d . {{_commit-recipes}} {{_ci-recipes}}
    just -f {{justfiles}}/shared.just -d . _no-bypass
    echo "QC-tooling push/CI checks completed"

# Scheduled, NOT in the PR/push gate: pre-existing repo-wide debt stays visible
# and reviewable without blocking unrelated PRs (#53), and is the non-blocking
# debt surface (#55) — no baseline/quarantine file silences anything; findings
# are reviewed and tracked as issues.
#
# public: AMBIENT audit — full-repo deferred-debt scan (complexity, dead code, duplication)
ambient:
    #!/usr/bin/env bash
    set -euo pipefail
    just -f {{justfiles}}/python.just -d . _ambient-python-debt
    echo "QC-tooling ambient debt audit completed"
