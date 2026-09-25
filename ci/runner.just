set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

control_repo := env_var("GITHUB_WORKSPACE")
infra := justfile_directory() / ".."

install-gate-tools:
    curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh

check-semantic-diff base_ref:
    #!/usr/bin/env bash
    set -euo pipefail
    cd {{control_repo}}
    uvx --from semgrep semgrep scan \
      --config={{infra}}/tool-configs/semgrep.yml \
      --baseline-commit="origin/{{base_ref}}" \
      --scan-unknown-extensions \
      --error

setup-profile profile:
    #!/usr/bin/env bash
    set -euo pipefail
    uv run --project {{infra}} ai-review-ci check-profile \
      --target "{{control_repo}}" \
      --profile "{{profile}}"
    case "{{profile}}" in
      python)
        uv sync --project "{{control_repo}}"
        ;;
      bun)
        cd "{{control_repo}}"
        bun install --frozen-lockfile
        ;;
      bun-python)
        uv sync --project "{{control_repo}}"
        cd "{{control_repo}}"
        bun install --frozen-lockfile
        ;;
      bun-playwright)
        cd "{{control_repo}}"
        bun install --frozen-lockfile
        bunx playwright install --with-deps
        ;;
      rust)
        cd "{{control_repo}}"
        cargo fetch
        ;;
      sage)
        if [ "${SAGE_BIN+x}" != x ]; then
          echo "ERROR: SAGE_BIN must be set for sage profile." >&2
          exit 1
        fi
        if [ ! -x "$SAGE_BIN" ]; then
          echo "ERROR: configured SAGE_BIN is not executable: $SAGE_BIN" >&2
          exit 1
        fi
        ;;
      *)
        echo "ERROR: unsupported project profile: {{profile}}" >&2
        exit 1
        ;;
    esac

check-delegation profile:
    uv run --project {{infra}} ai-review-ci check-delegation \
      --target "{{control_repo}}" \
      --profile "{{profile}}"

check-qc-doctor:
    #!/usr/bin/env bash
    set -euo pipefail

    doctor_payload="{{control_repo}}/.ai-review-ci-doctor.json"
    if uv run --project {{infra}} ai-review-ci doctor-ci \
      --target "{{control_repo}}" \
      --json > "$doctor_payload"; then
        doctor_status=0
    else
        doctor_status=$?
    fi

    printf '```ai-review-ci-doctor-json\n'
    cat "$doctor_payload"
    printf '\n```\n'
    exit "$doctor_status"

check-pr-description pr_number:
    uv run --project {{infra}} ai-review-ci check-pr-description \
      --repo "${GITHUB_REPOSITORY}" \
      --pr-number "{{pr_number}}" \
      --repo-root "{{control_repo}}"

check-app-boot profile:
    uv run --project {{infra}} ai-review-ci check-app-boot \
      --target "{{control_repo}}" \
      --profile "{{profile}}"

check-review-threads pr_number:
    uv run --project {{infra}} ai-review-ci check-review-threads \
      --repo "${GITHUB_REPOSITORY}" \
      --pr-number "{{pr_number}}" \
      --repo-root "{{control_repo}}"
