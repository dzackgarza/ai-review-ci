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

    mapfile -d '' -t doc_files < <(git ls-files -z -- '*.md' '*.html' '*.htm')
    if [ "${#doc_files[@]}" -eq 0 ]; then
        exit 0
    fi

    lychee --no-progress --include-fragments "${doc_files[@]}"

# Reformat Markdown and structured configuration before commit.
test-commit:
    @just --justfile {{ justfile() }} _format-structured-text

# Validate tracked documentation links before push.
test-push:
    @just --justfile {{ justfile() }} _check-links

# Validate tracked documentation links in CI.
test-ci:
    @just --justfile {{ justfile() }} _check-links
