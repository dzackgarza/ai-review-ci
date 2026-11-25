lfs_hooks_enabled() {
    if command -v git-lfs >/dev/null 2>&1; then
        return 0
    fi
    if git config --get-regexp '^filter\.lfs\.' >/dev/null; then
        echo "ai-review-ci hook: Git LFS is configured but git-lfs is not installed." >&2
        exit 1
    else
        lfs_config_status=$?
        [ "$lfs_config_status" -eq 1 ] || exit "$lfs_config_status"
    fi
    return 1
}
