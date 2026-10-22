#!/usr/bin/env bash
# Compatibility output for existing QC recipes. The caller retains the actual
# check status; ci-triage.py owns its log, finding IDs and burndown. A diagnostic
# is not an instruction to suspend the worker's current implementation task.
set -euo pipefail

case "${AI_REVIEW_CI_FAILURE_MODE:-direct}" in
  direct)
    cat <<'EOF'

QC FAILURE — explicitly invoked check returned a nonzero result.
See the preceding diagnostic for the specific failing condition.
This output does not change the current work objective or impose a workflow.
EOF
    ;;
  triage)
    cat <<'EOF'

QC FAILURE — CI diagnostic recorded; development publication is nonblocking.
The CI collector retains this check's failure, full log and identifiable
findings. Quality remediation belongs to a separately scheduled project phase;
the diagnostic does not redirect the current implementation task.
EOF
    ;;
  *)
    printf 'invalid AI_REVIEW_CI_FAILURE_MODE: %s\n' "$AI_REVIEW_CI_FAILURE_MODE" >&2
    exit 2
    ;;
esac
