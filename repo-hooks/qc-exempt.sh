# Shared exemption logic for the pre-commit and pre-push hooks. Sourced, not executed.
#
# Both hooks ask the same question — does this QC system govern this repository? — and
# the answer must not drift between them, so it is written once here.
#
# Sets qc_repo_root and qc_hook_repo for the caller, and defines qc_should_gate: returns
# 0 when the hook should run its gate, 1 when the repository is outside this system.

unset GIT_DIR GIT_INDEX_FILE GIT_WORK_TREE GIT_PREFIX GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_COMMON_DIR

qc_repo_root="$(git rev-parse --show-toplevel)"
qc_hook_file="$(readlink -f "$0")"
qc_hook_repo="$(CDPATH= cd -- "$(dirname -- "$qc_hook_file")/.." && pwd -P)"

qc_common_dir() {
	qc_dir="$(git -C "$1" rev-parse --git-common-dir)"
	case "$qc_dir" in
		/*) ;;
		*) qc_dir="$1/$qc_dir" ;;
	esac
	CDPATH= cd -- "$qc_dir" && pwd -P
}

# owner/name from either the SSH or the HTTPS form of a GitHub remote.
qc_github_slug() {
	printf '%s' "$1" | sed -E 's#^.*github\.com[:/]##; s#\.git$##'
}

# The owner this repository was forked from, or the empty string when it is not a fork.
#
# Fork-ness is a GitHub-side fact, so resolving it costs a network round trip. A hook runs
# on every commit, so the answer is cached in the clone's own config and resolved once.
# When it cannot be resolved — offline, no gh, unauthenticated — nothing is cached and
# the caller gates normally: an unknown answer must not become an exemption.
qc_upstream_owner() {
	if qc_cached="$(git -C "$qc_repo_root" config --get ai-review-ci.upstream-owner)"; then
		case "$qc_cached" in
			none) printf '' ;;
			*) printf '%s' "$qc_cached" ;;
		esac
		return 0
	fi
	qc_slug="$(qc_github_slug "$1")"
	if ! qc_parent="$(gh api "repos/$qc_slug" --jq 'if .fork then .parent.owner.login else "" end' 2>/dev/null)"; then
		return 1
	fi
	if [ -z "$qc_parent" ]; then
		git -C "$qc_repo_root" config --local ai-review-ci.upstream-owner none
	else
		git -C "$qc_repo_root" config --local ai-review-ci.upstream-owner "$qc_parent"
	fi
	printf '%s' "$qc_parent"
}

qc_should_gate() {
	# ai-review-ci's own tree: the gates run from CI and from its own recipes, not from
	# hooks that would recurse into the implementation under test.
	if [ "$(qc_common_dir "$qc_repo_root")" = "$(qc_common_dir "$qc_hook_repo")" ]; then
		return 1
	fi

	qc_remote="$(git -C "$qc_repo_root" config --get remote.origin.url 2>/dev/null || true)"

	# Wiki repositories carry GitHub's layout and never a justfile.
	case "${qc_repo_root##*/}" in
		*.wiki)
			echo "ai-review-ci hook: wiki repository — QC does not apply; proceeding without verification." >&2
			return 1
			;;
	esac
	case "$qc_remote" in
		*.wiki | *.wiki.git)
			echo "ai-review-ci hook: wiki repository — QC does not apply; proceeding without verification." >&2
			return 1
			;;
	esac

	case "$qc_remote" in
		"") return 0 ;;
		*dzackgarza/*) ;;
		*)
			echo "ai-review-ci hook: origin is not under the dzackgarza account — QC not owned here; proceeding without verification." >&2
			return 1
			;;
	esac

	# A fork of a third-party project sits under the account but is upstream's code: it
	# carries upstream's layout, will never be QC-wired, and is entirely exempt
	# (ai-review-ci#372). A fork of another repository in the account is still our code
	# and stays gated.
	if qc_parent_owner="$(qc_upstream_owner "$qc_remote")"; then
		case "$qc_parent_owner" in
			"" | dzackgarza) ;;
			*)
				echo "ai-review-ci hook: fork of $qc_parent_owner — upstream's code, QC not owned here; proceeding without verification." >&2
				return 1
				;;
		esac
	else
		echo "ai-review-ci hook: could not resolve fork status from GitHub; gating normally." >&2
		echo "  If this is a fork of a third-party project, record it once with:" >&2
		echo "    git config --local ai-review-ci.upstream-owner <upstream-owner>" >&2
	fi

	return 0
}
