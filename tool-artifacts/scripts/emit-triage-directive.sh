#!/usr/bin/env bash
# emit-triage-directive.sh
#
# Prints the standardized QC triage directive to stdout.
# Called by justfile recipes when a QC check fails.
# Does NOT exit - the caller handles the exit code.
#
# Usage:
#   "$QC_DIR/scripts/emit-triage-directive.sh"
#   exit 1  # or $ec

set -euo pipefail

cat << 'TRIAGE_EOF'

================================================================================
  QC FAILURE — TRIAGE REQUIRED
================================================================================

  One or more quality control checks failed (see above for details).

  YOU ARE NOW IN TRIAGE MODE. Follow these rules EXACTLY:

  1.  Do NOT probe, inspect, or modify any file in ~/ai-review-ci/.
      The QC configs, scripts, checking tools, and ML models are centrally
      owned and authoritative. Probing them is reward-hacking.

  2.  Do NOT attempt to fix any of the findings yourself.
      You WILL game the triage if you try. All fixes must be delegated
      to a subagent not involved in producing the failing code.

  3.  Present ALL findings to the user immediately, with the full raw
      tool output. Do NOT filter, summarize, or interpret the results.

  4.  Wait for explicit user approval before proceeding.

  TRIAGE WORKFLOW (after user approval):

    STEP 0 (MANDATORY, BEFORE SPAWNING ANYTHING) — Read the complete
    protocol and follow it exactly:

      reviewing-llm-code/references/qc-triage.md

    Routing gate (mechanical, no judgment calls):

    - Output already contains POLICY.* codes with file/line locations
      -> it IS the disposition artifact. Spawn ONLY a remediation
         subagent (Route C). That subagent loads
         policy-index/references/remediations.md + fixing-slop and
         derives the fix from the matching REMEDIATE.* entry.
         Do NOT spawn a reviewer/disposition subagent.

    - Output has no POLICY.* codes
      -> spawn a disposition subagent (Route B) that loads policy-index
         (with its references), anti-slop, reviewing-llm-code,
         bespoke-software-policy, and test-guidelines, and returns ONLY
         `VIOLATION -> POLICY.*` or `CLEARED` with quoted policy proof.
         B must NOT propose or imply any fix; a "false positive"
         disposition requires the formal policy-exception burden and is
         never a default. Then spawn a SEPARATE Route C remediation
         subagent for each violation.

    DISPATCH HYGIENE: subagent prompts carry ONLY the raw verbatim
    findings, file/line locations, and the skill-loading instructions
    above. Never include your own policy paraphrase, severity opinion,
    root-cause theory, remediation menu, or leaning. The orchestrator
    never adjudicates findings and never reads the remediation index.

================================================================================
TRIAGE_EOF
