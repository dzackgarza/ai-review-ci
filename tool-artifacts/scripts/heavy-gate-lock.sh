# Machine-wide advisory serialization for heavy QC gates.
#
# Sourced (never executed) as the first statement of a heavy recipe body:
#
#     _recipe:
#         #!/usr/bin/env bash
#         set -euo pipefail
#         source "{{artifacts}}/scripts/heavy-gate-lock.sh"
#         ...the gate, unchanged...
#
# WHY. One machine runs QC for every managed repository, and the heavy gates
# (test suites, Lean and Sage builds, semgrep / CodeQL / ML slop scans) have no
# knowledge of each other. When several overlap they oversubscribe the CPU, and
# an oversubscribed test suite fails on wall-clock timeouts rather than on
# defects: the same suite has produced 8, then 3, then 31 failures across three
# identical runs, with every sampled failure passing in isolation. A gate that
# reports random failures is worse than no gate, because a worker then has to
# disprove phantom regressions. Serializing the heavy gates removes the
# contention that manufactures those verdicts.
#
# WHAT THIS DOES NOT DO. It does not change what any gate checks, its pass/fail
# semantics, its output, or its exit code, and it imposes no time limit on a
# gate's own execution. It only decides when a gate is allowed to start.
#
# HOW THE LOCK IS RELEASED. The slot is held on an open file descriptor in the
# sourcing shell, so the kernel drops it when that shell exits — on success, on
# failure, on signal, and on kill -9 alike. There is no cleanup trap to leak and
# no stale lock file to clear by hand.
#
# ENVIRONMENT
#   AI_REVIEW_CI_HEAVY_GATE_JOBS
#       How many heavy gates may run at once, machine-wide. Default 1. Raise it
#       on a bigger box without editing any recipe.
#   AI_REVIEW_CI_HEAVY_GATE_LOCK_DIR
#       Directory holding the slot files. Default /tmp/ai-review-ci-heavy-gate.
#       It must be machine-wide, not per-repository — the whole point is that
#       unrelated repositories queue against each other.
#   AI_REVIEW_CI_HEAVY_GATE_WAIT
#       Seconds a queued gate will wait for a slot. Default 7200. This bounds
#       QUEUEING ONLY. Once a slot is acquired the gate runs to completion with
#       no time limit whatsoever, so a legitimately slow gate is never converted
#       into a failure. Exhausting this wait means a holder is stuck, which is
#       an operator problem and is reported as one.
#   AI_REVIEW_CI_HEAVY_GATE_HELD
#       Set by this script once a slot is held, and exported. A nested heavy
#       gate spawned underneath an existing holder inherits it and proceeds
#       without re-acquiring, so a composed gate cannot deadlock against itself.
#       Parent and child are one logical gate occupying one slot.

if ! (return 0 2>/dev/null); then
	echo "ERROR: heavy-gate-lock.sh must be sourced from a recipe body, not executed." >&2
	exit 1
fi

# Already inside a holder: this is the same logical gate, so take no new slot.
if [ -n "${AI_REVIEW_CI_HEAVY_GATE_HELD:-}" ]; then
	return 0
fi

_heavy_gate_jobs="${AI_REVIEW_CI_HEAVY_GATE_JOBS:-1}"
_heavy_gate_dir="${AI_REVIEW_CI_HEAVY_GATE_LOCK_DIR:-/tmp/ai-review-ci-heavy-gate}"
_heavy_gate_wait="${AI_REVIEW_CI_HEAVY_GATE_WAIT:-7200}"

if ! [[ "$_heavy_gate_jobs" =~ ^[1-9][0-9]*$ ]]; then
	echo "ERROR: AI_REVIEW_CI_HEAVY_GATE_JOBS must be a positive integer, got: '$_heavy_gate_jobs'" >&2
	exit 1
fi
if ! [[ "$_heavy_gate_wait" =~ ^[1-9][0-9]*$ ]]; then
	echo "ERROR: AI_REVIEW_CI_HEAVY_GATE_WAIT must be a positive integer number of seconds, got: '$_heavy_gate_wait'" >&2
	exit 1
fi
if ! command -v flock >/dev/null 2>&1; then
	echo "ERROR: flock is required to serialize heavy QC gates but is not on PATH." >&2
	echo "       Install util-linux; do not run heavy gates unserialized." >&2
	exit 1
fi

mkdir -p "$_heavy_gate_dir"

_heavy_gate_slot_file() {
	printf '%s/slot-%s.lock' "$_heavy_gate_dir" "$1"
}

# Try each slot without blocking. On success leaves the slot held on
# $_heavy_gate_fd for the lifetime of this shell.
_heavy_gate_try_slots() {
	local slot fd
	for ((slot = 1; slot <= _heavy_gate_jobs; slot++)); do
		# <> opens read-write WITHOUT truncating, so probing a slot never
		# erases the current holder's identity line.
		exec {fd}<>"$(_heavy_gate_slot_file "$slot")"
		if flock -n "$fd"; then
			_heavy_gate_fd="$fd"
			printf 'pid %s since %s (%s)\n' \
				"$$" "$(date -Is)" "$(pwd -P)" >"$(_heavy_gate_slot_file "$slot")"
			return 0
		fi
		exec {fd}>&-
	done
	return 1
}

_heavy_gate_report_holders() {
	local slot info
	for ((slot = 1; slot <= _heavy_gate_jobs; slot++)); do
		info="$(cat "$(_heavy_gate_slot_file "$slot")" 2>/dev/null || true)"
		if [ -n "$info" ]; then
			printf '#   slot %s held by %s\n' "$slot" "$info" >&2
		fi
	done
}

if _heavy_gate_try_slots; then
	export AI_REVIEW_CI_HEAVY_GATE_HELD="$$"
	return 0
fi

# Every slot is busy. Say so loudly and precisely: a silent stall here reads as
# a hang, and a worker who mistakes queueing for a hang kills the gate.
{
	echo "============================="
	echo "=== waiting for the machine-wide QC lock ==="
	echo "# All ${_heavy_gate_jobs} heavy-gate slot(s) are in use, so this gate is QUEUED, not hung."
	_heavy_gate_report_holders
	echo "# It starts as soon as a slot frees; it will wait up to ${_heavy_gate_wait}s."
	echo "# Heavy gates are serialized because concurrent ones oversubscribe the CPU"
	echo "# and turn timeouts into phantom test failures. Raise AI_REVIEW_CI_HEAVY_GATE_JOBS"
	echo "# to allow more at once on a larger machine."
} >&2

_heavy_gate_started_waiting="$(date +%s)"

if [ "$_heavy_gate_jobs" -eq 1 ]; then
	# Single slot: block in the kernel so the slot is handed over the instant
	# the holder exits, with no polling latency.
	exec {_heavy_gate_fd}<>"$(_heavy_gate_slot_file 1)"
	if flock -w "$_heavy_gate_wait" "$_heavy_gate_fd"; then
		printf 'pid %s since %s (%s)\n' \
			"$$" "$(date -Is)" "$(pwd -P)" >"$(_heavy_gate_slot_file 1)"
	else
		_heavy_gate_fd=""
	fi
else
	# Several slots: flock has no counting mode, so re-probe the slot set until
	# one frees or the queueing budget is spent.
	_heavy_gate_deadline=$((_heavy_gate_started_waiting + _heavy_gate_wait))
	_heavy_gate_fd=""
	while [ "$(date +%s)" -lt "$_heavy_gate_deadline" ]; do
		if _heavy_gate_try_slots; then
			break
		fi
		sleep 5
	done
fi

if [ -z "${_heavy_gate_fd:-}" ]; then
	{
		echo "ERROR: timed out after ${_heavy_gate_wait}s waiting for a machine-wide QC lock slot."
		echo "  This is a QUEUEING timeout, not a gate failure: the gate never started."
		echo "  A holder is very likely stuck. Current holders:"
		_heavy_gate_report_holders
		echo "  Resolve the stuck holder, or raise AI_REVIEW_CI_HEAVY_GATE_JOBS /"
		echo "  AI_REVIEW_CI_HEAVY_GATE_WAIT. Do not report this as a test regression."
	} >&2
	exit 1
fi

printf '# acquired the machine-wide QC lock after %ss of waiting.\n' \
	"$(($(date +%s) - _heavy_gate_started_waiting))" >&2

export AI_REVIEW_CI_HEAVY_GATE_HELD="$$"
