# Duration of one run of the global pre-commit or pre-push hook: the time its
# checks take for this single commit or push. Sourced first by each hook,
# before qc-exempt.sh, so exempt repositories are timed too. `$0` must be the
# hook itself.
#
# At exit, whatever the status, it prints this run's duration and appends it to
# <git-common-dir>/ai-review-ci/timing/hooks.jsonl. A failure to record fails
# the hook; scripts/hook-timing.py owns the format.

ai_review_ci_hook_start_ns=$(date +%s%N) || exit 1
ai_review_ci_hook_name=${0##*/}
ai_review_ci_hook_timing=$(dirname -- "$(readlink -f "$0")")/../scripts/hook-timing.py
# Resolve both locations before qc-exempt.sh clears the GIT_* variables, so a
# linked worktree records into the shared .git of its repository.
ai_review_ci_hook_git_dir=$(git rev-parse --path-format=absolute --git-common-dir) || exit 1
ai_review_ci_hook_worktree=$(git rev-parse --show-toplevel) || exit 1

ai_review_ci_hook_finish() {
	ai_review_ci_hook_status=$?
	trap - EXIT
	ai_review_ci_hook_end_ns=$(date +%s%N) || exit 1
	python3 "$ai_review_ci_hook_timing" \
		--git-dir "$ai_review_ci_hook_git_dir" \
		--hook "$ai_review_ci_hook_name" \
		--started-at-ns "$ai_review_ci_hook_start_ns" \
		--duration-ms "$(( (ai_review_ci_hook_end_ns - ai_review_ci_hook_start_ns) / 1000000 ))" \
		--exit-code "$ai_review_ci_hook_status" \
		--worktree "$ai_review_ci_hook_worktree" || exit 1
	exit "$ai_review_ci_hook_status"
}
trap ai_review_ci_hook_finish EXIT
