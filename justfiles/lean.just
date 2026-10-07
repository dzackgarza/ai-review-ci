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
#
# Lean compilation runs in CI only: the commit and push tiers are static scans.
# `test-ci` builds after fetching Mathlib's prebuilt cache, which Mathlib's
# `cache` tool keeps machine-wide in ~/.cache/mathlib, keyed by file hash.

# public: scan staged Lean source without compiling the project
test-commit: _lean-staged-check

# public: static Lean scans before push; no compilation
test-push: lean-no-sorry lean-semgrep

# public: build the project and run the full Lean gate in CI
test-ci: _lean-build lean-qc

[private]
_lean-staged-check:
	#!/usr/bin/env bash
	set -euo pipefail
	mapfile -d '' lean_files < <(git diff --cached --name-only --diff-filter=ACMR -z -- '*.lean')
	[ "${#lean_files[@]}" -gt 0 ] || {
		echo "No staged Lean files found"
		exit 0
	}
	for file in "${lean_files[@]}"; do
		git show ":$file" | python3 "{{artifacts}}/scripts/lean_sorry_scan.py" --stdin "$file" || {
			echo "ERROR: staged Lean source contains sorry declarations." >&2
			exit 1
		}
	done
	echo "Staged Lean source contains no sorry declarations"

[private]
_lean-build:
	#!/usr/bin/env bash
	set -euo pipefail
	source "{{artifacts}}/scripts/heavy-gate-lock.sh"
	if jq -e '.packages[] | select(.name == "mathlib")' lake-manifest.json >/dev/null; then
		lake exe cache get
	fi
	lake build

infra := justfile_directory() / ".."
justfiles := infra / "justfiles"
artifacts := infra / "tool-artifacts"

# public: fail when any tracked Lean source contains sorry (quarantine excluded)
lean-no-sorry:
	#!/usr/bin/env bash
	set -euo pipefail
	echo "=== Running: Lean no-sorry scan ==="
	# The shipped `answer(...)` elaborator (AiReviewCi/Answer.lean) legitimately
	# manipulates the `sorry` syntax; it carries no unproved proof. Consumers get it
	# under `.lake` (already unscanned); this glob also covers ai-review-ci's own tree
	# and any in-tree vendoring.
	# Comments and string literals are not proof terms: lean_sorry_scan.py skips them.
	rg_status=0
	files="$(rg --files --glob '*.lean' --glob '!*.conjecture*' --glob '!**/AiReviewCi/Answer.lean' .)" || rg_status=$?
	if [ "$rg_status" -gt 1 ]; then
		echo "ERROR: rg exited $rg_status; the sorry scan did not run." >&2
		exit "$rg_status"
	fi
	if [ -n "$files" ]; then
		mapfile -t lean_files <<<"$files"
		python3 "{{artifacts}}/scripts/lean_sorry_scan.py" "${lean_files[@]}" || {
			echo "ERROR: Lean source contains sorry declarations." >&2
			exit 1
		}
	fi
	echo "No sorry declarations in tracked Lean sources."

# public: run the shared semgrep gate (includes the Lean referent tripwires)
lean-semgrep:
	just -f {{justfiles}}/shared.just -d . _semgrep

# public: run the target's kernel-axiom audit from the target repository root
lean-axiom-audit:
	#!/usr/bin/env bash
	set -euo pipefail
	source "{{artifacts}}/scripts/heavy-gate-lock.sh"
	if ! just --dry-run _lean-axiom-audit >/dev/null 2>&1; then
		echo "ERROR: Lean QC requires a target-private _lean-axiom-audit recipe." >&2
		exit 1
	fi
	just _lean-axiom-audit

# public: the full composed Lean gate
lean-qc: lean-no-sorry lean-semgrep lean-axiom-audit
