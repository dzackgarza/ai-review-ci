# Shared Lean kernel-axiom audit.
#
# Lean projects keep their own build and test gates.  To use this recipe, the
# target justfile supplies `_lean-axiom-audit`, which must fail whenever its
# audited declarations depend on an axiom outside Lean's standard budget.

# public: run the target's kernel-axiom audit from the target repository root
lean-axiom-audit:
	#!/usr/bin/env bash
	set -euo pipefail
	if ! just --dry-run _lean-axiom-audit >/dev/null 2>&1; then
		echo "ERROR: Lean QC requires a target-private _lean-axiom-audit recipe." >&2
		exit 1
	fi
	just _lean-axiom-audit
