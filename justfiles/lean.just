# Shared Lean QC recipes.
#
# Lean projects keep their own build and test gates and delegate the
# language-level law here:
#   lean-no-sorry     — no `sorry` in tracked Lean sources (quarantine excluded)
#   lean-semgrep      — the shared semgrep gate, including the Lean referent
#                       tripwires (POLICY.NO_UNGROUNDED_MATH_NAME)
#   lean-axiom-audit  — the target-supplied kernel-axiom audit
#   lean-qc           — all of the above, composed
#
# The kernel audit stays target-supplied: checking the axiom closure of the
# built environment requires the repo's own root modules, so the target
# justfile provides `_lean-axiom-audit`, which must fail whenever its audited
# declarations depend on an axiom outside Lean's standard budget.
#
# `*.conjecture*` files are the sanctioned quarantine for statements exceeding
# the kernel axiom set (never imported or compiled into the library); the
# no-sorry scan excludes them like the semgrep axiom rule does.

infra := justfile_directory() / ".."
justfiles := infra / "justfiles"

# public: fail when any tracked Lean source contains sorry (quarantine excluded)
lean-no-sorry:
	#!/usr/bin/env bash
	set -euo pipefail
	echo "=== Running: Lean no-sorry scan ==="
	matches="$(rg -n --glob '*.lean' --glob '!*.conjecture*' '\bsorry\b' . || true)"
	if [ -n "$matches" ]; then
		echo "$matches"
		echo "ERROR: Lean source contains sorry declarations." >&2
		exit 1
	fi
	echo "No sorry declarations in tracked Lean sources."

# public: run the shared semgrep gate (includes the Lean referent tripwires)
lean-semgrep:
	just -f {{justfiles}}/shared.just -d . _semgrep

# public: run the target's kernel-axiom audit from the target repository root
lean-axiom-audit:
	#!/usr/bin/env bash
	set -euo pipefail
	if ! just --dry-run _lean-axiom-audit >/dev/null 2>&1; then
		echo "ERROR: Lean QC requires a target-private _lean-axiom-audit recipe." >&2
		exit 1
	fi
	just _lean-axiom-audit

# public: the full composed Lean gate
lean-qc: lean-no-sorry lean-semgrep lean-axiom-audit
