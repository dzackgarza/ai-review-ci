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
	#!/usr/bin/env bash
	set -euo pipefail
	just -f {{justfiles}}/python.just -d . test-commit
	just -f {{justfiles}}/bun.just -d . test-commit

# public: PUSH gate — both languages' push checks and test suites
test-push:
	#!/usr/bin/env bash
	set -euo pipefail
	just -f {{justfiles}}/python.just -d . test-push
	just -f {{justfiles}}/bun.just -d . test-push

# public: CI gate — both languages' CI gates, then the cross-language stack once
test-ci:
	#!/usr/bin/env bash
	set -euo pipefail
	export AI_REVIEW_CI_FAILURE_MODE=triage
	just -f {{justfiles}}/python.just -d . _ci-checks
	just -f {{justfiles}}/bun.just -d . _ci-checks
	just -f {{justfiles}}/shared.just -d . _global-qc
	echo "CI quality checks completed"

# Scheduled, never in the PR/push gate: the whole-tree scans. The commit tier
# scans staged files and test-ci the diff, so this is the only whole-tree semgrep.
# Every step runs; the audit fails if any did.
#
# public: AMBIENT audit — whole-tree semgrep and debt scan
ambient:
	#!/usr/bin/env bash
	set -uo pipefail
	export AI_REVIEW_CI_FAILURE_MODE=triage
	status=0
	just -f {{justfiles}}/shared.just -d . _ambient-semgrep || status=1
	just -f {{justfiles}}/python.just -d . _ambient-python-debt || status=1
	just -f {{justfiles}}/bun.just -d . _ambient-bun-debt || status=1
	[ "$status" -eq 0 ] || exit 1
	echo "Bun/Python ambient audit completed"
