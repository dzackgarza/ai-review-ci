# Development: local commit/push check staged syntax only; CI owns suites and quality debt.
# ai-review-ci docs-and-configs QC implementation.
# Markdown is reformatted with Flowmark at commit tier; tracked Markdown and HTML links
# are validated with Lychee at push and CI tiers.

import "./shared.just"

_check-links:
    #!/usr/bin/env bash
    set -euo pipefail

    if ! command -v lychee >/dev/null 2>&1; then
        echo "FATAL: docs-and-configs QC requires lychee; install it from https://github.com/lycheeverse/lychee" >&2
        exit 1
    fi

    # Markdown/HTML under a test directory is fixture/spec data (intentional
    # broken links and adversarial inputs live there), not authored docs, so it is
    # not link-scanned. By artifact kind, uniform across projects.
    mapfile -d '' -t doc_files < <(git ls-files -z -- '*.md' '*.html' '*.htm' ':(glob,exclude)**/tests/**' ':(glob,exclude)**/test/**' ':(glob,exclude)**/__tests__/**')
    if [ "${#doc_files[@]}" -eq 0 ]; then
        exit 0
    fi

    lychee --no-progress --include-fragments "${doc_files[@]}"

# Reformat Markdown and structured configuration before commit.
test-commit:
    @python3 "{{justfile_directory()}}/../scripts/local-check.py"

# Validate tracked documentation links before push.
test-push:
    @python3 "{{justfile_directory()}}/../scripts/local-check.py" --mode push

# Validate tracked documentation links in CI.
test-ci:
    @python3 "{{justfile_directory()}}/../scripts/ci-triage.py" docs-and-configs
