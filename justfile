qc-type := "python"
repo := justfile_directory()
home := home_directory()
global_hooks_source_dir := repo / "global-hooks"
repo_hooks_source_dir := repo / "repo-hooks"
global_hooks_dir := env_var_or_default("GIT_GLOBAL_HOOKS_DIR", home / ".config/git/hooks")

# Parse-check every infrastructure source: workflow YAML, runner justfile, shell wrappers
check:
    python3 -c "import ast, pathlib; [ast.parse(p.read_text()) for p in pathlib.Path('src').rglob('*.py')]; [ast.parse(p.read_text()) for p in pathlib.Path('tests').rglob('*.py')]"
    python3 -c "import yaml, pathlib; yaml.safe_load(pathlib.Path('.github/workflows/_review.yml').read_text())"
    just -f ci/runner.just --list >/dev/null
    just -f justfiles/shared.just --list >/dev/null
    just -f justfiles/python.just --list >/dev/null
    just -f justfiles/bun.just --list >/dev/null
    just -f justfiles/rust.just --list >/dev/null
    just -f justfiles/sage.just --list >/dev/null
    bash -n ci/private/submit-candidate
    sh -n ci/reviewer_home/bin/submit-candidate
    sh -n global-hooks/pre-commit
    sh -n global-hooks/pre-push
    sh -n repo-hooks/pre-commit
    sh -n repo-hooks/pre-push

# Full quality gate: routes through the global QC chain for Python projects
test:
    just -f {{repo}}/justfiles/python.just -d . test

# Install the trigger workflows into a target repo
install target=".":
    uvx --from . ai-review-ci install --target {{target}}

# Install globally managed Git hooks for this user.
install-global-hooks:
    #!/usr/bin/env bash
    set -euo pipefail

    for hook in pre-commit pre-push; do
        source="{{ global_hooks_source_dir }}/$hook"
        if [[ ! -x "$source" ]]; then
            echo "Error: missing executable global hook source: $source"
            exit 1
        fi
    done

    mkdir -p "{{ global_hooks_dir }}"

    for hook in pre-commit pre-push; do
        source="{{ global_hooks_source_dir }}/$hook"
        target="{{ global_hooks_dir }}/$hook"
        if [[ -e "$target" && ! -L "$target" ]]; then
            echo "Error: refusing to replace non-symlink global hook: $target"
            exit 1
        fi
        ln -snf "$source" "$target"
    done

    git config --global core.hooksPath "{{ global_hooks_dir }}"
    git config --global core.hooksPath

# Install repo-local hook symlinks into a target repository.
install-repo-hooks target=".":
    #!/usr/bin/env bash
    set -euo pipefail

    target_repo="{{target}}"
    hooks_dir="$(git -C "$target_repo" rev-parse --git-path hooks)"
    case "$hooks_dir" in
        /*) ;;
        *) hooks_dir="$target_repo/$hooks_dir" ;;
    esac
    mkdir -p "$hooks_dir"

    for hook in pre-commit pre-push; do
        source="{{ repo_hooks_source_dir }}/$hook"
        if [[ ! -x "$source" ]]; then
            echo "Error: missing executable repo hook source: $source"
            exit 1
        fi
        target_path="$hooks_dir/$hook"
        if [[ -e "$target_path" && ! -L "$target_path" ]]; then
            echo "Error: refusing to replace non-symlink repo hook: $target_path"
            exit 1
        fi
        ln -snf "$source" "$target_path"
    done

    echo "$hooks_dir"
