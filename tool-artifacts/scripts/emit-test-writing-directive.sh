#!/usr/bin/env bash
# Compatibility output when a diagnostic recipe finds missing tests.
# Test planning is independently scheduled; this notice has no control-plane
# authority to change the current workstream or demand subagent deployment.
set -euo pipefail

case "${AI_REVIEW_CI_FAILURE_MODE:-direct}" in
  direct)
    cat <<'EOF'

QC FAILURE — the explicitly invoked project-test preflight found no tests.
See the preceding diagnostic; no change of work objective is implied.
EOF
    ;;
  triage)
    cat <<'EOF'

QC FAILURE — CI recorded missing project-test coverage.
This is a development diagnostic, not a local publication gate or a mandate
to interrupt current implementation. The later test phase owns remediation.
EOF
    ;;
  *)
    printf 'invalid AI_REVIEW_CI_FAILURE_MODE: %s\n' "$AI_REVIEW_CI_FAILURE_MODE" >&2
    exit 2
    ;;
esac
