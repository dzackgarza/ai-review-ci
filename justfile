qc-type := "qc-tooling"
repo := justfile_directory()
global_hooks_source_dir := repo / "global-hooks"
repo_hooks_source_dir := repo / "repo-hooks"
scaffold_source_dir := repo / "scaffolds"
skills_source_dir := repo / "skills"

# Normalize infrastructure files before parse checks inspect them
_normalize:
    just -f {{repo}}/justfiles/shared.just -d . _format-structured-text

[private]
_check-yaml:
    python3 -c "import yaml, pathlib; [yaml.safe_load(p.read_text()) for p in pathlib.Path('.github/workflows').glob('*.yml')]; [yaml.safe_load(p.read_text()) for p in pathlib.Path('src/ai_review_ci/templates').glob('*.yml')]"

# Parse-check every infrastructure source: workflow YAML, runner justfile, shell wrappers
check: _normalize
    python3 -c "import ast, pathlib; [ast.parse(p.read_text()) for p in pathlib.Path('src').rglob('*.py')]; [ast.parse(p.read_text()) for p in pathlib.Path('tests').rglob('*.py')]"
    just --justfile {{justfile()}} -d . _check-yaml
    just -f ci/runner.just --list >/dev/null
    just -f justfiles/shared.just --list >/dev/null
    just -f justfiles/python.just --list >/dev/null
    just -f justfiles/qc-tooling.just --list >/dev/null
    just -f justfiles/bun.just --list >/dev/null
    just -f justfiles/rust.just --list >/dev/null
    just -f justfiles/sage.just --list >/dev/null
    bash -n ci/private/submit-candidate
    sh -n ci/reviewer_home/bin/submit-candidate
    bash -n tool-artifacts/scripts/emit-test-writing-directive.sh
    sh -n global-hooks/pre-commit
    sh -n global-hooks/pre-push
    sh -n repo-hooks/pre-commit
    sh -n repo-hooks/pre-push

# Check that skill markdown links are checkout-relative and resolvable.
check-skill-links:
    uv run tool-artifacts/scripts/check_skill_links.py

# Commit gate: immediate, directly repairable feedback.
test-commit:
    just -f {{repo}}/justfiles/qc-tooling.just -d . test-commit

# Push gate: commit checks plus the full project-owned test suite.
test-push:
    just -f {{repo}}/justfiles/qc-tooling.just -d . test-push

# CI gate: push checks plus changed-line coverage / dependency / import
# boundary checks. This repo does not self-apply the downstream slop stack.
test-ci:
    just -f {{repo}}/justfiles/qc-tooling.just -d . test-ci

# Ambient gate: full-repo deferred-debt audit, run on a schedule (ambient.yml),
# never in the PR/push gate. Delegates to the qc-tooling profile.
ambient:
    just -f {{repo}}/justfiles/qc-tooling.just -d . ambient

# gh-boundary gate: the label suite's real-boundary tests that authenticate to
# the live GitHub API. Isolated from the three standard gates so GH_TOKEN is scoped to
# this recipe's CI step alone (_qc.yml), never exported to the QC tier's recipes
# and npx/uvx tool runners (#218). `-m gh_boundary` overrides the default
# `not gh_boundary` deselection in pyproject.
test-gh-boundary:
    uvx --python 3.14 --with pytest --with-editable . pytest -m gh_boundary

# Install the complete QC enforcement surface into a target repo.
install repo branch profile target=".":
    uvx --from . ai-review-ci install --target {{target}} --repo {{repo}} --branch {{branch}} --profile {{profile}}

# Create/update the canonical label taxonomy on a target repo (idempotent).
install-labels repo:
    uvx --from . ai-review-ci install-labels --repo {{repo}}

# Install globally managed Git hooks for this user.
install-global-hooks:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ "${GIT_GLOBAL_HOOKS_DIR+x}" != x ]]; then
        echo "ERROR: GIT_GLOBAL_HOOKS_DIR must be set to the global Git hooks directory."
        exit 1
    fi
    global_hooks_dir="$GIT_GLOBAL_HOOKS_DIR"

    for hook in pre-commit pre-push; do
        source="{{ global_hooks_source_dir }}/$hook"
        if [[ ! -x "$source" ]]; then
            echo "Error: missing executable global hook source: $source"
            exit 1
        fi
    done

    mkdir -p "$global_hooks_dir"

    for hook in pre-commit pre-push; do
        source="{{ global_hooks_source_dir }}/$hook"
        target="$global_hooks_dir/$hook"
        if [[ -e "$target" && ! -L "$target" ]]; then
            echo "Error: refusing to replace non-symlink global hook: $target"
            exit 1
        fi
        ln -snf "$source" "$target"
    done

    git config --global core.hooksPath "$global_hooks_dir"
    git config --global core.hooksPath

# Symlink every skill in skills/ into the user's skills directory (AI_SKILLS_DIR).
install-skills:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ "${AI_SKILLS_DIR+x}" != x ]]; then
        echo "ERROR: AI_SKILLS_DIR must be set to your skills directory (e.g. ~/ai/opencode/skills). Set it in ~/.envrc."
        exit 1
    fi
    skills_dir="$AI_SKILLS_DIR"
    mkdir -p "$skills_dir"

    for skill in "{{ skills_source_dir }}"/*/; do
        skill="${skill%/}"
        name="$(basename "$skill")"
        target="$skills_dir/$name"
        if [[ -e "$target" && ! -L "$target" ]]; then
            echo "Error: refusing to replace non-symlink skill: $target"
            exit 1
        fi
        ln -snf "$skill" "$target"
        echo "$target -> $skill"
    done

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

# Copy a repo-local QC delegation scaffold into a target repository.
install-qc-scaffold profile target=".":
    #!/usr/bin/env bash
    set -euo pipefail

    case "{{profile}}" in
        python|bun|bun-playwright|bun-python|docs-and-configs|rust|sage) ;;
        *)
            echo "Error: profile must be one of: python, bun, bun-playwright, bun-python, docs-and-configs, rust, sage"
            exit 1
            ;;
    esac

    source_dir="{{ scaffold_source_dir }}/{{profile}}"
    target_repo="{{target}}"

    if [[ ! -d "$source_dir" ]]; then
        echo "Error: missing scaffold source: $source_dir"
        exit 1
    fi
    if [[ ! -d "$target_repo" ]]; then
        echo "Error: target repository directory does not exist: $target_repo"
        exit 1
    fi

    while IFS= read -r -d '' source_file; do
        relative_path="${source_file#$source_dir/}"
        target_path="$target_repo/$relative_path"
        if [[ -e "$target_path" ]]; then
            echo "Error: refusing to overwrite existing scaffold target: $target_path"
            exit 1
        fi
    done < <(find "$source_dir" -type f -print0)

    cp -R "$source_dir/." "$target_repo/"
    echo "$target_repo"
