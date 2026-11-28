unset GIT_DIR GIT_WORK_TREE GIT_PREFIX GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_COMMON_DIR

qc_directives_dir="$HOME/ai/hooks"

qc_print_directive() {
	qc_doc="$qc_directives_dir/$1.md"
	if [ -f "$qc_doc" ]; then
		cat "$qc_doc" >&2
	else
		echo "ai-review-ci hook: missing hook directive document: $qc_doc" >&2
	fi
}

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

qc_github_slug() {
	printf '%s' "$1" | sed -E 's#^.*github\.com[:/]##; s#\.git$##'
}

qc_upstream_owner() {
    if qc_cached="$(git -C "$qc_repo_root" config --get ai-review-ci.upstream-owner)"; then
        case "$qc_cached" in
            none) printf '' ;;
            *) printf '%s' "$qc_cached" ;;
        esac
        return 0
    fi
    return 1
}

qc_has_gate_recipes() {
    for qc_justfile in "$qc_repo_root"/[Jj][Uu][Ss][Tt][Ff][Ii][Ll][Ee] "$qc_repo_root"/.[Jj][Uu][Ss][Tt][Ff][Ii][Ll][Ee]; do
        [ -f "$qc_justfile" ] || continue
        if just --show test-commit >/dev/null 2>&1 || just --show test-push >/dev/null 2>&1; then
            return 0
        fi
        if ! just --summary >/dev/null; then
            echo "ai-review-ci hook: cannot inspect fork's justfile; gating normally." >&2
            return 0
        fi
        return 1
    done
    return 1
}

qc_should_gate() {
	if [ "$(qc_common_dir "$qc_repo_root")" = "$(qc_common_dir "$qc_hook_repo")" ]; then
		return 1
	fi

	qc_remote="$(git -C "$qc_repo_root" config --get remote.origin.url 2>/dev/null || true)"

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

	if qc_parent_owner="$(qc_upstream_owner "$qc_remote")"; then
		case "$qc_parent_owner" in
			"" | dzackgarza) ;;
			*)
				if qc_has_gate_recipes; then
					return 0
				fi
				echo "ai-review-ci hook: fork of $qc_parent_owner — no local QC gate recipes; proceeding without verification." >&2
				return 1
				;;
		esac
	else
		echo "ai-review-ci hook: fork status not locally configured; gating normally." >&2
		echo "  If this is a fork of a third-party project, record it once with:" >&2
		echo "    git config --local ai-review-ci.upstream-owner <upstream-owner>" >&2
	fi

	return 0
}
