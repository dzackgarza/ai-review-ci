# Development: local commit/push check staged syntax only; CI owns suites and quality debt.
# justfile-bun-python — QC for a repository with both a Python and a Bun project
#
# Composes python.just and bun.just. A bun-python repository delegates to this file:
#   just -f ~/ai-review-ci/justfiles/bun-python.just -d . test-commit
#
# The cross-language stack (`_global-qc` in shared.just) scans the whole caller
# repository whatever its languages, so test-ci runs it once, after both
# languages' own CI gates.

infra := justfile_directory() / ".."
justfiles := infra / "justfiles"

# public: COMMIT gate — both languages' commit checks
test-commit:
    @python3 "{{justfile_directory()}}/../scripts/local-check.py"

# public: PUSH gate — both languages' push checks and test suites
test-push:
    @python3 "{{justfile_directory()}}/../scripts/local-check.py"

# public: CI gate — both languages' CI gates, then the cross-language stack once
test-ci:
    @python3 "{{justfile_directory()}}/../scripts/ci-triage.py" bun-python

# Scheduled, never in the PR/push gate: the whole-tree scans. The commit tier
# scans staged files and test-ci the diff, so this is the only whole-tree semgrep.
# Every step runs; the audit fails if any did.
#
# public: AMBIENT audit — whole-tree semgrep and debt scan
ambient:
    @python3 "{{justfile_directory()}}/../scripts/ci-triage.py" bun-python --tier ambient
