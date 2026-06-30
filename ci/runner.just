set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

control_repo := env_var("GITHUB_WORKSPACE")
infra := justfile_directory() / ".."
reviewer_home := "/home/reviewer"
reviewer_repo := "/home/reviewer/repo"
review_defs := "/home/reviewer/.review"
reviewer_infra := "/home/reviewer/.review/infra"
private_tools := "/opt/ai-review/private"

install-tools:
    curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh
    npm install -g opencode-ai
    npm install -g cc-safety-net

install-gate-tools:
    curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh

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

fetch-context tool_name pr_number:
    uv run --project {{infra}} ai-review-ci fetch-context \
      --repo "${GITHUB_REPOSITORY}" \
      --tool-names "{{tool_name}}" \
      --output "{{control_repo}}/.reviewer-context.md" \
      --alerts-output "{{control_repo}}/.reviewer-alerts.json" \
      --pr-number "{{pr_number}}"

create-reviewer:
    if reviewer_entry="$(getent passwd reviewer)"; then \
      IFS=: read -r name _ uid gid gecos home shell <<< "$reviewer_entry"; \
      if [ "$name" != "reviewer" ]; then echo "expected reviewer account, got $name" >&2; exit 1; fi; \
      if [ "$home" != "{{reviewer_home}}" ]; then echo "reviewer home mismatch: $home" >&2; exit 1; fi; \
      if [ "$shell" != "/bin/bash" ]; then echo "reviewer shell mismatch: $shell" >&2; exit 1; fi; \
    else \
      sudo useradd -m -s /bin/bash reviewer; \
    fi
    sudo rm -rf {{reviewer_home}}/repo
    sudo mkdir -p {{reviewer_home}}/repo
    sudo chown -R reviewer:reviewer {{reviewer_home}}

install-private-tools:
    sudo rm -rf {{private_tools}}
    sudo mkdir -p {{private_tools}}
    sudo rsync -a --exclude '.venv' {{infra}}/ {{private_tools}}/
    sudo uv sync --project {{private_tools}}
    sudo chown -R root:root {{private_tools}}
    sudo chmod 700 {{private_tools}}
    sudo chmod 500 {{private_tools}}/ci/private/submit-candidate

install-reviewer-home:
    sudo rsync -a --delete {{infra}}/ci/reviewer_home/ {{reviewer_home}}/
    sudo mkdir -p {{reviewer_infra}}
    sudo rsync -a --delete --exclude '.venv' {{infra}}/ {{reviewer_infra}}/
    sudo chown -R reviewer:reviewer {{reviewer_home}}
    sudo chmod 755 {{reviewer_home}}/bin/submit-candidate
    sudo -u reviewer -H uv sync --project {{reviewer_infra}}

install-sudo-rule:
    { echo "reviewer ALL=(root) NOPASSWD: {{private_tools}}/ci/private/submit-candidate"; \
      echo "reviewer ALL=(root) NOPASSWD: {{private_tools}}/ci/private/submit-candidate *"; \
      echo "Defaults!{{private_tools}}/ci/private/submit-candidate env_keep += \"REPORT_TYPE REVIEWER_REPO CONTROL_REPO\""; \
    } | sudo tee /etc/sudoers.d/ai-review-submit >/dev/null
    sudo chmod 0440 /etc/sudoers.d/ai-review-submit
    sudo visudo -c -f /etc/sudoers.d/ai-review-submit

copy-reviewer-repo:
    sudo rsync -a --delete \
      --exclude '.git' \
      --exclude '.github' \
      --exclude '.agents' \
      --exclude '.hermes' \
      --exclude '.review-report-artifact.json' \
      --exclude '.review-report.sarif' \
      {{control_repo}}/ {{reviewer_repo}}/
    sudo mkdir -p {{reviewer_repo}}/.agents/review-runner/candidates
    sudo cp {{control_repo}}/.reviewer-context.md {{reviewer_repo}}/.reviewer-context.md
    sudo chown -R reviewer:reviewer {{reviewer_repo}}

prepare:
    just -f {{infra}}/ci/runner.just create-reviewer
    just -f {{infra}}/ci/runner.just install-private-tools
    just -f {{infra}}/ci/runner.just install-reviewer-home
    just -f {{infra}}/ci/runner.just install-sudo-rule
    just -f {{infra}}/ci/runner.just copy-reviewer-repo

stage-pr-diff base_ref:
    git -C {{control_repo}} diff "origin/{{base_ref}}...HEAD" > "${RUNNER_TEMP}/reviewer-diff.patch"
    test -s "${RUNNER_TEMP}/reviewer-diff.patch"
    if [ -d "{{reviewer_repo}}" ]; then \
      sudo cp "${RUNNER_TEMP}/reviewer-diff.patch" {{reviewer_repo}}/.reviewer-diff.patch; \
      sudo chown reviewer:reviewer {{reviewer_repo}}/.reviewer-diff.patch; \
    fi

check-deterministic-diff:
    uv run --project {{infra}} ai-review-ci check-diff \
      --diff "${RUNNER_TEMP}/reviewer-diff.patch"

check-delegation profile:
    uv run --project {{infra}} ai-review-ci check-delegation \
      --target "{{control_repo}}" \
      --profile "{{profile}}"

check-qc-doctor:
    #!/usr/bin/env bash
    set -euo pipefail

    doctor_payload="{{control_repo}}/.ai-review-ci-doctor.json"
    if uv run --project {{infra}} ai-review-ci doctor \
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
      --pr-number "{{pr_number}}"

check-app-boot profile:
    uv run --project {{infra}} ai-review-ci check-app-boot \
      --target "{{control_repo}}" \
      --profile "{{profile}}"

check-review-threads pr_number:
    uv run --project {{infra}} ai-review-ci check-review-threads \
      --repo "${GITHUB_REPOSITORY}" \
      --pr-number "{{pr_number}}"

run-review report_type scope:
    sudo -u reviewer -H env \
      PATH="{{reviewer_home}}/bin:/usr/bin:/bin" \
      HOME="{{reviewer_home}}" \
      XDG_CONFIG_HOME="{{reviewer_home}}/.config" \
      XDG_DATA_HOME="{{reviewer_home}}/.local/share" \
      XDG_STATE_HOME="{{reviewer_home}}/.local/state" \
      XDG_CACHE_HOME="{{reviewer_home}}/.cache" \
      REPORT_TYPE="{{report_type}}" \
      REVIEWER_REPO="{{reviewer_repo}}" \
      CONTROL_REPO="{{control_repo}}" \
      bash -lc 'cd {{reviewer_repo}} && /usr/local/bin/opencode --version && /usr/local/bin/uv run --project {{reviewer_infra}} ai-review-ci run-review \
        --template "{{reviewer_infra}}/reviews/{{report_type}}/template.md" \
        --scope "{{reviewer_infra}}/reviews/scope-{{scope}}.md" \
        --manifest "{{reviewer_infra}}/reviews/{{report_type}}/manifest.txt" \
        --reviewer-context .reviewer-context.md'

collect-output:
    cp {{reviewer_repo}}/.review-report-artifact.json {{control_repo}}/.review-report-artifact.json

convert-sarif category:
    uv run --project {{infra}} ai-review-ci to-sarif \
      --artifact "{{control_repo}}/.review-report-artifact.json" \
      --output "{{control_repo}}/.review-report.sarif" \
      --carry-forward-alerts "{{control_repo}}/.reviewer-alerts.json" \
      --category "{{category}}"

post-threads pr_number:
    uv run --project {{infra}} ai-review-ci post-threads \
      --artifact "{{control_repo}}/.review-report-artifact.json" \
      --diff "${RUNNER_TEMP}/reviewer-diff.patch" \
      --repo "${GITHUB_REPOSITORY}" \
      --pr-number "{{pr_number}}"
